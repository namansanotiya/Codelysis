# Graph-RAG Code Impact Analyzer: End-to-End System Explanation Guide

This document provides a comprehensive, step-by-step breakdown of the **Graph-RAG Code Change Impact Analysis & Co-Change Recommender** system. It is structured sequentially according to the project's data processing pipeline for use in technical presentations, code walkthroughs, and project defense.

---

## 📋 Pipeline Overview

```text
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│  1. Ingestion   │ ──► │ 2. Parsing & AST Analysis│ ──► │3. Relation Filtering│
└─────────────────┘     └──────────────────────────┘     └─────────────────────┘
                                                                    │
                                                                    ▼
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│ 6. RAG Serial-  │ ◄── │  5. Ego-Graph & k-Hop    │ ◄── │4. Graph Construction│
│    ization      │     │     Traversal (with Graph│     │   G = (V, E)        │
└────────┬────────┘     └──────────────────────────┘     └─────────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────────────┐
│ 7. LLM Reasoning│ ──► │  8. Data Schema &        │
│    & Report     │     │     Parsed Structures    │
└─────────────────┘     └──────────────────────────┘
```

---

## 1. 📥 Ingestion

The ingestion phase is responsible for acquiring source code files from the repository and extracting incoming changes (Git diffs).

### 1.1 Repository File Ingestion (`graph_builder.py: scan_repo_files`)
- **Directory Traversal**: The system recursively scans the target repository path using `os.walk()`.
- **Ignore Rules**: To avoid processing third-party libraries, build artifacts, or temporary files, vendor directories listed in `IGNORED_DIRS` are excluded:
  `{"node_modules", ".git", "venv", ".venv", "env", "dist", "build", "__pycache__", ".next", "out", "target", "vendor", "coverage", ".pytest_cache"}`
- **Extension Filter**: Only files matching `SUPPORTED_EXTENSIONS` are ingested:
  - Python: `.py`
  - JavaScript / TypeScript: `.js`, `.jsx`, `.ts`, `.tsx`
  - Java: `.java`
  - C / C++: `.c`, `.cpp`, `.h`, `.hpp`
  - Go: `.go`

### 1.2 Git Diff Ingestion (`diff_parser.py: get_git_diff & parse_unified_diff`)
- **Unified Diff Retrieval**: Executes `git diff HEAD` (or `git diff HEAD~1 HEAD` for recent commits) using `subprocess.run()`. Alternatively, accepts a custom diff string supplied via CLI/API.
- **Hunk Parsing**: Parses unified diff hunk headers using regular expressions:
  `^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@`
- **Line Mapping**: Maps modified files to their changed line numbers in the new file version:
  ```python
  file_changes: Dict[str, Set[int]] = {
      "auth/service.py": {3, 4, 5}
  }
  ```

---

## 2. 🔍 Parsing and AST Analysis

The parsing phase analyzes the raw source code of ingested files to identify structural definitions (classes, functions, methods) and invocation reference sites (function calls, method invocations).

### 2.1 Python AST Visitor (`graph_builder.py: PythonASTVisitor`)
For Python files (`.py`), the system uses Python's native `ast` module to build an Abstract Syntax Tree (AST):
- **`visit_ClassDef(node)`**: Registers class definitions and pushes class name onto the scope stack.
- **`visit_FunctionDef(node)` / `visit_AsyncFunctionDef(node)`**:
  - Inspects the scope stack (`current_scope`). If inside a class scope, categorizes symbol as `method`; otherwise, categorizes as `function`.
  - Captures full qualified names (e.g., `CoreProcessor.process_request`).
- **`visit_Call(node)`**:
  - Traverses invocation expressions (`node.func`). Identifies simple calls (`Name`) and attribute calls (`Attribute`, e.g. `obj.method()`).
  - Records reference call nodes along with line numbers and enclosing container identifiers.

### 2.2 Multi-Language Pattern Parser (`graph_builder.py: parse_generic_source`)
For JavaScript, TypeScript, Java, C/C++, and Go, a pattern parser uses compiled regular expressions:
1. **Class / Interface / Struct Regex**:
   `^\s*(?:export\s+)?(?:public|private|protected\s+)?(?:class|interface|struct|type)\s+([A-Za-z0-9_]+)`
2. **Function / Method Definition Regex**:
   `^\s*(?:export\s+)?(?:async\s+)?(?:public|private|protected|static|virtual|inline|func|function\s+)?(?:[A-Za-z0-9_*&<>\[\],:]+\s+)+([A-Za-z0-9_]+)\s*\([^;{]*\)`
3. **Invocation Call Site Regex**:
   `\b([A-Za-z0-9_]+)\s*\(`

---

## 3. 🧹 Relation Filtering

Without filtering, repository graphs become polluted with noise from standard libraries, built-in keywords, and control flow structures.

### 3.1 Keyword & Standard Library Exclusion Filter (`config.py: STDLIB_MODULES` & `BUILTIN_KEYWORDS`)
- **Control Flow Filter**: Language control flow statements (`if`, `else`, `for`, `while`, `switch`, `case`, `try`, `catch`, `return`) are explicitly excluded from definition and call site parsing using `CONTROL_FLOW_PREFIXES`.
- **Standard Library Modules**: Python standard modules (`os`, `sys`, `json`, `math`, `typing`, `logging`, `unittest`), JS/TS built-ins (`console`, `require`, `import`, `export`), Java/C++/Go built-ins (`System`, `out`, `println`, `fmt`, `Printf`) are excluded.
- **Built-in Functions**: Primitive types and built-in functions (`str`, `int`, `len`, `range`, `make`, `append`, `sizeof`) are stripped out.

### 3.2 Internal Relationship Isolation
By filtering out external calls, the graph only registers edges between internal project components. An invocation `console.log("hello")` or `len(items)` is discarded, while `validate_token(token)` is retained for internal dependency resolution.

---

## 4. 🕸️ Graph Construction

The graph builder constructs a Directed Dependency Graph $G = (V, E)$ using NetworkX (`nx.DiGraph`).

### 4.1 Node Schema ($V$)
Each node represents a code entity or line site:
```python
@dataclass
class CodeNode:
    node_id: str      # Format: "rel_path:L<line>:<type>:<name>"
    file: str         # Relative file path (e.g. "auth/service.py")
    line: int         # 1-indexed line number
    name: str         # Symbol identifier (e.g. "validate_token")
    type: str         # 'def' (definition site) or 'ref' (reference call site)
    category: str     # 'file', 'class', 'function', 'method', 'call'
    snippet: str      # Source code line text
```

### 4.2 Edge Schema ($E$)
1. **`E_contain` (Structural Containment Edge)**:
   - Connects a parent container node to an inner definition or reference node.
   - Examples: `File Node -> Function Node`, `Class Node -> Method Node`, `Function Node -> Call Reference Node`.
2. **`E_invoke` (Invocation Dependency Edge)**:
   - Connects a call reference node (`ref`) to its corresponding definition target node (`def`).
   - Example: `auth/service.py:L14:ref:validate_token` $\xrightarrow{E\_invoke}$ `auth/service.py:L3:def:validate_token`.

### 4.3 Two-Pass Assembly Algorithm

```text
PASS 1: Scan Source Files
 ├── Create File Nodes
 ├── Register Definition Nodes (def) -> Store in symbol_defs dict
 └── Add E_contain Edges (File -> Class/Function)

PASS 2: Resolve Call Sites
 ├── Iterate over Reference Nodes (ref)
 ├── Add E_contain Edges (Enclosing Container -> ref Node)
 └── Look up called symbol in symbol_defs:
      └── Match Found? -> Add E_invoke Edge (ref Node -> Target def Node)
```

---

## 5. 🧭 Ego-Graph Traversal and $k$-Hop Traversal

Once graph $G = (V, E)$ is built, the system extracts a localized $k$-hop **Ego Subgraph** $G_{ego}$ around modified code.

### 5.1 Seed Node Identification (`diff_parser.py: extract_seed_nodes`)
1. Modified line numbers parsed from the Git diff are matched against nodes in $G$.
2. Nodes falling on or near changed lines ($\pm 2$ lines) are designated as **Seed Nodes** $S \subseteq V$.

### 5.2 $k$-Hop Bidirectional BFS Traversal Algorithm (`impact_analyzer.py: extract_ego_graph`)

Starting from seed nodes $S$, the algorithm performs a bidirectional Breadth-First Search (BFS) up to distance $k$:
- **Forward Traversal (Successors)**: Follows outgoing edges to discover callees and internal definitions.
- **Backward Traversal (Predecessors)**: Follows incoming edges to discover callers, parent functions, classes, and enclosing files.

```text
                      [Hop 2: Indirect Callers & Tests]
                                    ▲
                                    │ E_contain / E_invoke
                      [Hop 1: Direct Callers (ref Nodes)]
                                    ▲
                                    │ E_invoke
                         ★ [SEED NODE S (Modified def)] ★
                                    │
                                    │ E_contain / E_invoke
                                    ▼
                          [Hop 1: Direct Callees]
```

### 5.3 Detailed Traversal Flow Diagram

```mermaid
flowchart TD
    subgraph Legend
        Seed["★ Seed Node (Modified Code)"]
        Hop1["Hop 1 (Direct Callers / Callees)"]
        Hop2["Hop 2 (Indirect Callers / Test Suites)"]
    end

    subgraph Traversal Architecture
        S["auth/service.py:L3:def:validate_token"] :::seedStyle

        %% Forward Hop 1
        S -->|E_contain| C1["auth/token.py:L1:def:decode_token"] :::hop1Style

        %% Backward Hop 1 (Direct Call Sites)
        R1["auth/service.py:L14:ref:validate_token"] :::hop1Style -->|E_invoke| S
        R2["core/service.py:L6:ref:validate_token"] :::hop1Style -->|E_invoke| S
        R3["tests/test_auth.py:L5:ref:validate_token"] :::hop1Style -->|E_invoke| S

        %% Backward Hop 2 (Enclosing Caller Functions/Classes)
        F1["auth/service.py:L12:def:login_user"] :::hop2Style -->|E_contain| R1
        F2["core/service.py:L4:def:CoreProcessor.process_request"] :::hop2Style -->|E_contain| R2
        F3["tests/test_auth.py:L4:def:test_validate_token_success"] :::hop2Style -->|E_contain| R3
    end

    classDef seedStyle fill:#ff9999,stroke:#cc0000,stroke-width:3px,color:#000;
    classDef hop1Style fill:#ffcc99,stroke:#ff6600,stroke-width:2px,color:#000;
    classDef hop2Style fill:#99ccff,stroke:#0066cc,stroke-width:2px,color:#000;
```

---

### 5.4 Step-by-Step Traversal Examples

#### Example 1: 1-Hop Backward Traversal (Discovering Direct Callers)
- **Starting Seed Node**: `auth/service.py:L3:def:validate_token`
- **Incoming Edges Checked**: System inspects `graph.predecessors(seed_node)`.
- **Discovered Nodes**:
  1. `core/service.py:L6:ref:validate_token` (Call site inside core service)
  2. `tests/test_auth.py:L5:ref:validate_token` (Call site inside unit test)
- **Traversal Action**: Both call sites are added to $G_{ego}$ at **Hop 1**.

#### Example 2: 2-Hop Backward Traversal (Discovering Enclosing Functions & Test Cases)
- **Frontier Nodes at Hop 1**: `core/service.py:L6:ref:validate_token`, `tests/test_auth.py:L5:ref:validate_token`
- **Incoming Edges Checked**: System inspects `graph.predecessors(call_site)`.
- **Discovered Nodes**:
  1. `core/service.py:L4:def:CoreProcessor.process_request` (Parent Method containing call)
  2. `tests/test_auth.py:L4:def:test_validate_token_success` (Parent Test Function)
- **Traversal Action**: Parent definition nodes are added to $G_{ego}$ at **Hop 2**.

#### Example 3: 1-Hop Forward Traversal (Discovering Callees)
- **Starting Seed Node**: `auth/service.py:L3:def:validate_token`
- **Outgoing Edges Checked**: System inspects `graph.successors(seed_node)`.
- **Discovered Nodes**: `auth/service.py:L5:ref:decode_token` $\xrightarrow{E\_invoke}$ `auth/token.py:L1:def:decode_token`.
- **Traversal Action**: `decode_token` is added to $G_{ego}$ as a callee dependency.

---

## 6. 📝 RAG Serialization

The RAG Engine (`graph_rag_engine.py`) flattens the extracted graph $G_{ego}$ into a structured text prompt for LLM ingestion.

### 6.1 Text Context Serialization Protocol
`serialize_ego_graph()` formats $G_{ego}$ into clean Markdown sections:
1. **Git Diff Header**: Contains modified source lines.
2. **Modified Seed Symbols**: Lists affected function/class definitions along with code snippets.
3. **Repository Subgraph Hierarchy**: Groups nodes by **FILE $\to$ Symbol Category $\to$ Code Snippet $\to$ Inbound Callers $\to$ Outbound Calls**.

### 6.2 Example Serialized Output Format
```text
=== GRAPH-RAG REPOSITORY SUBGRAPH CONTEXT ===

--- GIT DIFF / CHANGED CODE ---
--- a/auth/service.py
+++ b/auth/service.py
@@ -3,4 +3,4 @@
-def validate_token(token: str) -> bool:
+def validate_token(token: str, require_admin: bool = False, tenant_id: str = "default") -> bool:

--- MODIFIED SEED SYMBOLS ---
- SEED: [FUNCTION] validate_token (File: auth/service.py, Line: 3)
  Code: `def validate_token(token: str, require_admin: bool = False, tenant_id: str = "default") -> bool:`

--- REPOSITORY DEPENDENCY SUBGRAPH ---
FILE: auth/service.py
  FUNCTION: validate_token [MODIFIED SEED] (Line 3)
    Called by:
      - login_user (auth/service.py:14)

FILE: core/service.py
  METHOD: CoreProcessor.process_request (Line 4)
    Code: def process_request(self, token: str, payload: dict) -> dict:
    Calls:
      - validate_token (auth/service.py:3)

FILE: tests/test_auth.py
  FUNCTION: test_validate_token_success (Line 4)
    Code: def test_validate_token_success():
    Calls:
      - validate_token (auth/service.py:3)
```

### 6.3 Token Guardrails (`MAX_CONTEXT_SIZE = 8000`)
To prevent LLM context window overflow and high latency, `serialize_ego_graph()` enforces an 8,000-character ceiling, truncating lower-priority leaves if exceeded.

---

## 7. 🤖 LLM Reasoning & Report Generation

The Recommender Engine (`recommender.py`) feeds the serialized Graph-RAG context to an LLM or fallback engine to produce co-change impact reports.

### 7.1 LLM Prompt Architecture (`graph_rag_engine.py: build_llm_prompts`)
- **System Prompt**: Assigns role as Software Architect & Code Change Impact Analyzer.
- **User Prompt**: Instructs model to analyze signature shifts, caller invocation mismatches, required refactorings, and test updates.

### 7.2 Multi-Provider & Fallback Architecture
1. **Google Gemini API**: Queries `gemini-2.5-flash` using `google-genai` SDK when `GEMINI_API_KEY` is present.
2. **OpenAI API**: Queries `gpt-4o` when `OPENAI_API_KEY` is present.
3. **Rule-Based Fallback Engine**: If no API key is provided, `generate_compact_recommendation_report()` executes deterministically over $G_{ego}$, generating a file-grouped impact summary:

```markdown
# Code Change Impact Analysis — Affected Files Summary

### 1. Modified Seed Files
- **auth/service.py**: `validate_token` (Line 3)

### 2. Files Requiring Co-Changes (4 Files Impacted)

#### 📁 `auth/service.py`
- **Impact Level:** High (Direct Invocation)
- **Affected Lines:** Line 12, Line 14
- **Affected Symbols:** `login_user`, `validate_token`
- **Action Required:** Update call arguments to match modified function signature.

#### 📁 `core/service.py`
- **Impact Level:** High (Direct Invocation)
- **Affected Lines:** Line 4, Line 6
- **Affected Symbols:** `CoreProcessor.process_request`, `validate_token`
- **Action Required:** Update call arguments to match modified function signature.

#### 📁 `tests/test_auth.py`
- **Impact Level:** High (Direct Invocation)
- **Affected Lines:** Line 4, Line 5
- **Affected Symbols:** `test_validate_token_success`, `validate_token`
- **Action Required:** Update call arguments to match modified function signature.

#### 📁 `auth/token.py`
- **Impact Level:** Medium (2-hop Dependency)
- **Affected Lines:** Line 1
- **Affected Symbols:** `decode_token`
- **Action Required:** Re-verify workflow integration & execute tests.
```

---

## 8. 📊 What Data We Are Parsing (Data Schema & Parsed Structures)

### 8.1 Input Data (Git Diff Payload)
```text
--- a/auth/service.py
+++ b/auth/service.py
@@ -3,4 +3,4 @@
-def validate_token(token: str) -> bool:
+def validate_token(token: str, require_admin: bool = False, tenant_id: str = "default") -> bool:
```

### 8.2 AST Node Structure (`CodeNode` Data Class)
```json
{
  "node_id": "auth/service.py:L3:def:validate_token",
  "file": "auth/service.py",
  "line": 3,
  "name": "validate_token",
  "type": "def",
  "category": "function",
  "snippet": "def validate_token(token: str, require_admin: bool = False) -> bool:"
}
```

### 8.3 NetworkX Internal Edge Structure
```json
{
  "source": "core/service.py:L6:ref:validate_token",
  "target": "auth/service.py:L3:def:validate_token",
  "edge_type": "E_invoke"
}
```

### 8.4 Impact Analysis Summary Payload (`impact_summary`)
```json
{
  "seed_nodes": [
    { "node_id": "auth/service.py:L3:def:validate_token", "file": "auth/service.py", "line": 3, "name": "validate_token" }
  ],
  "direct_callers": [
    { "node_id": "core/service.py:L4:def:CoreProcessor.process_request", "file": "core/service.py", "line": 4, "name": "CoreProcessor.process_request" },
    { "node_id": "tests/test_auth.py:L4:def:test_validate_token_success", "file": "tests/test_auth.py", "line": 4, "name": "test_validate_token_success" }
  ],
  "indirect_callers": [],
  "callees": [
    { "node_id": "auth/token.py:L1:def:decode_token", "file": "auth/token.py", "line": 1, "name": "decode_token" }
  ],
  "affected_files": ["auth/service.py", "auth/token.py", "core/service.py", "tests/test_auth.py"],
  "total_ego_nodes": 11,
  "total_ego_edges": 11
}
```
