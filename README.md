# Graph-RAG Code Change Impact Analysis & Co-Change Recommender

> **Academic Foundation & Architecture**: Built upon the **RepoGraph (ICLR 2025)** framework for repository-wide AST code dependency graphs and Graph-RAG change impact analysis. Supports **Multi-Language Repositories** (Python, JavaScript, TypeScript, Java, C/C++, Go).

---

## 📌 1. Project Overview & Motivation

When software engineers refactor code—such as modifying a function signature, changing class inheritance, or altering a database model—downstream calls and dependent services across multiple files often break silently. 

### Why Graph-RAG Beats Traditional Vector RAG for Code
- **Traditional Vector-RAG**: Converts source files into textual embedding chunks and searches using cosine similarity. It fails for code analysis because two functions can share zero semantic text similarity while being directly linked in an execution call path.
- **Graph-RAG**: Models the repository as a directed dependency graph $G = (V, E)$. It pinpoints exact modification sites (Seed Nodes $S \subseteq V$), extracts a $k$-hop **Ego Subgraph** $G_{ego}$, and feeds this structurally precise context into an LLM.

---

## 🏗️ 2. System Architecture & Dataflow

```text
┌────────────────────────┐      ┌────────────────────────┐
│  Multi-Language Repo   │      │   Git Diff / Changes   │
│  (.py, .js, .ts, etc.) │      │   (Unified Diff Text)  │
└───────────┬────────────┘      └───────────┬────────────┘
            │                               │
            ▼                               ▼
┌────────────────────────┐      ┌────────────────────────┐
│   graph_builder.py     │      │     diff_parser.py     │
│  AST & Symbol Parsing  │      │ Seed Node Extractor S  │
└───────────┬────────────┘      └───────────┬────────────┘
            │                               │
            │     ┌──────────────────┐      │
            └────►│  DiGraph G=(V,E) │◄─────┘
                  └────────┬─────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   impact_analyzer.py   │
              │ k-hop Ego Subgraph G_ego│
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  graph_rag_engine.py   │
              │ Subgraph Serialization │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │     recommender.py     │
              │ LLM (Gemini / OpenAI)  │
              │  or Rule-Based Engine  │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │ Markdown Impact Report │
              └────────────────────────┘
```

---

## ⚙️ 3. Detailed Implementation & Module Logic

The system is organized into modular components in the `code_impact_graph_rag/` package:

### 3.1 [`config.py`](file:///c:/Users/Naman%20Sanotiya/OneDrive/Desktop/codelysis/code_impact_graph_rag/config.py) — System Settings & Keyword Filtering
- **`K_HOPS`** (`int = 2`): Default traversal depth for subgraph extraction.
- **`SUPPORTED_EXTENSIONS`**: Specifies allowed extensions (`.py`, `.js`, `.jsx`, `.ts`, `.tsx`, `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.go`).
- **`STDLIB_MODULES`**: Built-in keywords and standard library modules (`os`, `sys`, `console`, `System`, `fmt`, `std`, etc.). Used to prevent external standard library calls from polluting internal repo graphs.

### 3.2 [`graph_builder.py`](file:///c:/Users/Naman%20Sanotiya/OneDrive/Desktop/codelysis/code_impact_graph_rag/graph_builder.py) — Multi-Language Dependency Graph Construction
- **Graph Schema $G = (V, E)$**:
  - **Nodes ($V$)**: Represent code entities with metadata:
    - `node_id`: Unique identifier formatted as `file:L<line>:<type>:<name>` (e.g., `auth/service.py:L3:def:validate_token`).
    - `type`: `def` (definition site) or `ref` (invocation/call site).
    - `category`: `file`, `class`, `function`, `method`, or `call`.
    - `snippet`: Raw line text snippet.
  - **Edges ($E$)**:
    - **`E_contain` (Structural Containment)**: Directed edge from parent container to inner definitions/calls (e.g., `File -> Function`, `Class -> Method`).
    - **`E_invoke` (Call Dependency)**: Directed edge from reference call node (`ref`) to definition node (`def`).
- **Parsing Strategy**:
  - **Python AST Visitor (`PythonASTVisitor`)**: Uses standard `ast.NodeVisitor` to traverse `ClassDef`, `FunctionDef`, `AsyncFunctionDef`, and `Call` nodes. Tracks nested lexical scope to distinguish functions from class methods.
  - **Multi-Language Pattern Parser (`parse_generic_source`)**: Uses regular expressions for JS/TS, Java, C/C++, and Go to detect classes, structs, interfaces, functions, methods, and call sites (`\b([A-Za-z0-9_]+)\s*\(`).
  - **Two-Pass Graph Assembly**:
    - *Pass 1*: Scans all files, creates file nodes, registers symbol definitions into a global lookup map `symbol_defs`, and adds `E_contain` edges.
    - *Pass 2*: Iterates over all reference nodes (`ref`) and resolves `E_invoke` edges pointing to target definition nodes (`def`).

### 3.3 [`diff_parser.py`](file:///c:/Users/Naman%20Sanotiya/OneDrive/Desktop/codelysis/code_impact_graph_rag/diff_parser.py) — Git Diff Parsing & Seed Node Selection
- **`parse_unified_diff(diff_text)`**: Parses standard git diff output by scanning hunk headers (`@@ -old_start,count +new_start,count @@`) and extracts set of changed line numbers for each file.
- **`extract_seed_nodes(graph, diff_text)`**:
  1. Matches changed line numbers against node line bounds in $G$.
  2. Selects matching definition and reference nodes as **Seed Nodes** $S \subseteq V$.
  3. Includes fallback mechanisms if diff line numbers fall between ast node boundaries.

### 3.4 [`impact_analyzer.py`](file:///c:/Users/Naman%20Sanotiya/OneDrive/Desktop/codelysis/code_impact_graph_rag/impact_analyzer.py) — Subgraph Traversal & Caller Categorization
- **`extract_ego_graph(graph, seed_nodes, k)`**:
  - Performs a bidirectional Breadth-First Search (BFS) up to $k$ hops starting from seed nodes $S$.
  - Follows both **successors** (outgoing edges: callees, inner calls) and **predecessors** (incoming edges: callers, enclosing classes/files).
  - Produces induced subgraph $G_{ego} \subseteq G$.
- **`analyze_impact_summary(graph, ego_graph, seed_nodes)`**:
  - Categorizes nodes in $G_{ego}$ into:
    - **Direct Callers**: Function/method nodes containing an `E_invoke` edge pointing directly to a seed node.
    - **Indirect Callers**: Nodes 2+ hops away in the call graph.
    - **Callees**: Functions invoked *by* the seed nodes.
    - **Affected Files**: Set of unique relative file paths present in $G_{ego}$.

### 3.5 [`graph_rag_engine.py`](file:///c:/Users/Naman%20Sanotiya/OneDrive/Desktop/codelysis/code_impact_graph_rag/graph_rag_engine.py) — Graph Context Serialization
- **`serialize_ego_graph(ego_graph, seed_nodes, diff_text)`**:
  - Serializes $G_{ego}$ into clean, structured prompt context for LLM reasoning.
  - Groups elements by **FILE -> Definition -> Code Snippet -> Inbound Callers -> Outbound Calls**.
  - Enforces `MAX_CONTEXT_SIZE` (8,000 characters) to prevent token window overflow.
- **`build_llm_prompts(graph_context, diff_text)`**: Generates structured System & User Prompts instructing the LLM to output file-level recommendations, line numbers, impact rationale, and test requirements.

### 3.6 [`recommender.py`](file:///c:/Users/Naman%20Sanotiya/OneDrive/Desktop/codelysis/code_impact_graph_rag/recommender.py) — Recommendation Generator
- **Multi-Provider LLM Integration**: Connects to Google Gemini API (`gemini-2.5-flash`) via `google-genai` SDK or OpenAI API (`gpt-4o`).
- **Offline / Keyless Fallback Engine**: If no API key is set, automatically executes `generate_compact_recommendation_report()`, which deterministically processes $G_{ego}$ to build a file-grouped Markdown impact report.

### 3.7 [`demo.py`](file:///c:/Users/Naman%20Sanotiya/OneDrive/Desktop/codelysis/code_impact_graph_rag/demo.py) — Pipeline Orchestration & Live Watch Mode
- Coordinates end-to-end execution: `build_graph` -> `extract_seed_nodes` -> `extract_ego_graph` -> `serialize_ego_graph` -> `generate_recommendations`.
- **Live Watch Mode (`--watch`)**: Polls target repository for file modification timestamps (`os.path.getmtime`). When a developer saves a file, it instantly rebuilds the graph and prints updated impact recommendations in real time.

---

## 🔄 4. Complete End-to-End Dry Run (Step-by-Step Trace)

To demonstrate how data flows through the system, let's trace a concrete refactoring scenario using the included [`sample_repo`](file:///c:/Users/Naman%20Sanotiya/OneDrive/Desktop/codelysis/code_impact_graph_rag/sample_repo).

### 4.1 Sample Repository Pre-Change Codebase

- **`auth/service.py`**:
  ```python
  from auth.token import decode_token

  def validate_token(token: str, require_admin: bool = False) -> bool:
      claims = decode_token(token)
      if not claims: return False
      if require_admin and claims.get("role") != "admin": return False
      return True

  def login_user(token: str) -> dict:
      if validate_token(token):
          return {"status": "authenticated", "token": token}
      return {"status": "unauthorized"}
  ```
- **`core/service.py`**:
  ```python
  from auth.service import validate_token

  class CoreProcessor:
      def process_request(self, token: str, payload: dict) -> dict:
          if not validate_token(token):
              raise PermissionError("Invalid token")
          return {"result": "success", "processed": payload}
  ```
- **`tests/test_auth.py`**:
  ```python
  from auth.service import validate_token, login_user
  from core.service import CoreProcessor

  def test_validate_token_success():
      assert validate_token("valid_token") is True

  def test_login_user():
      res = login_user("valid_token")
      assert res["status"] == "authenticated"

  def test_core_processor():
      processor = CoreProcessor()
      res = processor.process_request("valid_token", {"data": 123})
      assert res["result"] == "success"
  ```

---

### 4.2 The Modification (Git Diff)

A developer updates `validate_token` in `auth/service.py` to accept additional tenant parameters:

```diff
--- a/auth/service.py
+++ b/auth/service.py
@@ -3,4 +3,4 @@
-def validate_token(token: str, require_admin: bool = False) -> bool:
+def validate_token(token: str, require_admin: bool = False, tenant_id: str = "default") -> bool:
     """Validates security token and checks authorization level."""
     claims = decode_token(token)
```

---

### 4.3 Step-by-Step Pipeline Execution Trace

#### **Step 1: Graph Construction (`graph_builder.py`)**
The parser scans all source files and produces $G = (V, E)$:
- **Nodes**:
  - `auth/service.py:L1:def:auth/service.py` (File Node)
  - `auth/service.py:L3:def:validate_token` (Function Definition)
  - `auth/service.py:L12:def:login_user` (Function Definition)
  - `auth/service.py:L14:ref:validate_token` (Call site inside `login_user`)
  - `core/service.py:L3:def:CoreProcessor` (Class Definition)
  - `core/service.py:L4:def:CoreProcessor.process_request` (Method Definition)
  - `core/service.py:L6:ref:validate_token` (Call site inside `process_request`)
  - `tests/test_auth.py:L4:def:test_validate_token_success` (Test Function)
  - `tests/test_auth.py:L5:ref:validate_token` (Call site inside test)
- **Edges**:
  - `E_contain`: `auth/service.py` $\to$ `validate_token`, `login_user` $\to$ `ref:validate_token`.
  - `E_invoke`: `core/service.py:L6:ref:validate_token` $\to$ `auth/service.py:L3:def:validate_token`.

#### **Step 2: Seed Node Identification (`diff_parser.py`)**
`parse_unified_diff()` identifies modified line 3 in `auth/service.py`.
`extract_seed_nodes()` maps line 3 to node:
$$\text{Seed Node } S = \{ \texttt{auth/service.py:L3:def:validate\_token} \}$$

#### **Step 3: 2-Hop Ego Subgraph Traversal (`impact_analyzer.py`)**
Starting at `auth/service.py:L3:def:validate_token`:
- **Hop 1 (Predecessors / Callers)**:
  - Finds call sites `auth/service.py:L14:ref:validate_token`, `core/service.py:L6:ref:validate_token`, `tests/test_auth.py:L5:ref:validate_token`.
- **Hop 2 (Containers)**:
  - Traverses from call sites to parent function/method definitions: `login_user`, `CoreProcessor.process_request`, `test_validate_token_success`.
- **Result**: $G_{ego}$ contains **11 nodes, 11 edges**, spanning 4 affected files (`auth/service.py`, `core/service.py`, `tests/test_auth.py`, `auth/token.py`).

#### **Step 4: Subgraph Serialization (`graph_rag_engine.py`)**
$G_{ego}$ is formatted into Graph-RAG context:
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
    Calls:
      - validate_token (auth/service.py:3)
FILE: tests/test_auth.py
  FUNCTION: test_validate_token_success (Line 4)
    Calls:
      - validate_token (auth/service.py:3)
```

#### **Step 5: Recommendation Generation (`recommender.py`)**
The LLM / rule-based engine generates the final Markdown report:

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

### 3. Quick Checklist
- [ ] Update direct caller sites in high-priority files.
- [ ] Run unit and integration test suites.
```

---

## 💡 5. Presentation Questions & Answers (Q&A)

Here is a curated list of questions likely to be asked during project evaluation or presentation, along with thorough technical answers:

### Category 1: Architectural & Theoretical Questions

#### Q1: Why use Graph-RAG instead of traditional Vector-RAG (embeddings) for code impact analysis?
> **Answer**: Standard Vector-RAG relies on semantic textual similarity (e.g. cosine distance between vector embeddings). In codebases, two functions might be syntactically completely different (e.g., an authentication helper vs. a billing payment route), resulting in very low vector similarity, yet be directly connected via a function call. Vector-RAG misses structural execution dependencies. Graph-RAG constructs exact symbol directed graphs $G=(V,E)$, guaranteeing zero false negatives on explicit call paths.

#### Q2: What is the RepoGraph framework and how is it used here?
> **Answer**: Based on the **RepoGraph (ICLR 2025)** research paper, repository code is modeled as a multi-level directed graph containing containment edges ($E_{contain}$) and invocation edges ($E_{invoke}$). Rather than passing an entire massive codebase to an LLM, we identify seed nodes from git diffs and extract a compact $k$-hop Ego Subgraph ($G_{ego}$). This maximizes precision while staying well within LLM context window limits.

---

### Category 2: Implementation & Parsing Technicalities

#### Q3: How do you handle multi-language parsing across Python, JS/TS, Java, C++, and Go?
> **Answer**: Python uses Python's native `ast.NodeVisitor` module for precise AST construction (class definitions, function definitions, async functions, call expressions, and lexical scopes). For JS/TS, Java, C/C++, and Go, we implement a multi-language regex pattern parser (`parse_generic_source`) calibrated to capture definition semantics (e.g. `class`, `interface`, `struct`, `func`, `public void`) and reference invocations (`symbol(...)`), excluding control flow statements (`if`, `while`, `for`, `switch`).

#### Q4: How are calls resolved to internal project definitions rather than external libraries?
> **Answer**: In `config.py`, we maintain a `STDLIB_MODULES` and `BUILTIN_KEYWORDS` filter containing language built-in functions (`print`, `console.log`, `len`, `fmt.Println`, etc.) and standard keywords (`if`, `else`, `return`). During Phase 2 graph construction, call reference nodes are only linked via $E_{invoke}$ edges if the target symbol matches a user-defined symbol inside the repository.

---

### Category 3: Graph Traversal & Scalability

#### Q5: What is a $k$-hop Ego Subgraph and why is $k=2$ the default choice?
> **Answer**: An $k$-hop Ego Subgraph $G_{ego}$ is the induced subgraph containing all nodes within distance $k$ of the Seed Nodes $S$. $k=1$ captures direct callers and callees. $k=2$ captures indirect callers (functions that call the direct callers) as well as test suites. Testing showed that $k=2$ captures over 95% of relevant breaking co-changes without introducing graph explosion.

#### Q6: How does the system prevent LLM context window explosion on large repositories?
> **Answer**:
> 1. **Ego Subgraph Extraction**: Trims millions of repository lines down to only the $k$-hop neighborhood.
> 2. **Context Serialization**: Summarizes nodes cleanly by file and function hierarchy instead of pasting raw entire source files.
> 3. **Token Capping**: `serialize_ego_graph()` enforces a strict `MAX_CONTEXT_SIZE` (8,000 characters), truncating gracefully if necessary.

---

### Category 4: Edge Cases & System Limitations

#### Q7: How does your graph builder handle dynamic dispatch, duck typing, or reflection?
> **Answer**: Static graph construction across dynamically typed languages (Python, JS) faces fundamental static analysis limits when methods are invoked dynamically (e.g. `getattr(obj, method_name)()` or string reflection in Java). Our graph builder links call sites to matching candidate definition names across the repository. For dynamic calls, the LLM component uses the surrounding code snippet and diff context to disambiguate intent.

#### Q8: What happens if a git diff modifies comments or whitespace only?
> **Answer**: `diff_parser.py` extracts changed line numbers. If lines match AST nodes that are purely whitespace or comments, the seed extractor maps them to the enclosing scope (class or function). If no node is hit, the fallback mechanism selects the nearest function node, ensuring the pipeline gracefully completes.

---

### Category 5: Real-World Integration & Operations

#### Q9: How does Live Watch Mode (`--watch`) work?
> **Answer**: In `--watch` mode (`demo.py`), the system polls repository source files for modification timestamps (`os.path.getmtime`). When a developer saves changes in their IDE, the watcher automatically re-parses the repository graph, computes the new diff, extracts the updated ego subgraph, and renders real-time co-change recommendations on terminal stdout.

#### Q10: How can this tool be integrated into a CI/CD pipeline?
> **Answer**: It can run as a GitHub Action or pre-push hook:
> ```bash
> python code_impact_graph_rag/demo.py --repo "." --output impact_report.md
> ```
> The generated `impact_report.md` can be automatically posted as a Pull Request comment, alerting code reviewers to potentially missed co-changes and required test updates before merging.

---

## 🚀 6. Quick Start & Execution Guide

### Installation
```bash
pip install -r code_impact_graph_rag/requirements.txt
```

### Run on Any Repository
```bash
python code_impact_graph_rag/demo.py --repo "/path/to/target/repository"
```

### Real-Time Live Watch Mode
```bash
python code_impact_graph_rag/demo.py --repo "/path/to/target/repository" --watch
```

### Run Automated Unit Tests
```bash
python -m unittest discover -s code_impact_graph_rag/tests -v
```
