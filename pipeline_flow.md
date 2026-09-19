# Codelysis Pipeline & Data Flow Architecture

This document details how a repository (from GitHub or local storage) transitions through each phase of the Codelysis Graph-RAG pipeline, the exact data structures produced at each step, and the modules responsible.

---

## 1. End-to-End Pipeline Overview

```
 [ GitHub API / Local Repo ]
             │
             ▼  Phase 1: Ingestion & Source Loading
    Dict[str, str] (File Contents) + Unified Git Diff
             │
             ▼  Phase 2: Multi-Language AST Parsing & Symbol Extraction
    List[CodeNode] (Defs, Refs, File Nodes)
             │
             ▼  Phase 3: Line-Level Dependency Graph Construction
    NetworkX DiGraph: G = (V, E)
             │
             ▼  Phase 4: Diff Parsing & Seed Node Mapping
    List[CodeNode] (Modified Seed Nodes S ⊂ V)
             │
             ▼  Phase 5: k-Hop Ego-Graph Traversal & Impact Analysis
    Ego-Graph G_ego + ImpactSummary (Direct/Indirect Callers, Files)
             │
             ▼  Phase 6: Graph-RAG Serialization & Prompt Synthesis
    Serialized Graph Context + System & User Prompts
             │
             ▼  Phase 7: LLM Reasoning & Co-Change Recommendations
    Structured Impact Analysis Report (Markdown)
```

---

## 2. Phase-by-Phase Data Flow & Transformations

### Phase 1: Ingestion & Source Loading
* **Responsible Module:** `sources/github_client.py` (`GitHubClient`) or `sources/local_loader.py` (`LocalLoader`)
* **What it does:** Fetches all repository files and the active Git diff without requiring full repository cloning when using GitHub API.
* **Input Data:**
  * GitHub repo slug (`"owner/repo"`), optional `pr_number` (int) or `commit_sha` (str), GitHub Token.
  * *OR* Local directory path (`/path/to/repo`).
* **Output Data Structures:**
  1. `file_contents: Dict[str, str]`
     * Key: Relative file path (e.g., `"auth/service.py"`)
     * Value: Raw file content as UTF-8 string
  2. `diff_text: str`
     * Unified Git diff string containing added/removed hunks (`@@ -old +new @@`).

---

### Phase 2: Multi-Language Parsing & Symbol Extraction
* **Responsible Module:** `parsers/`
  * `parsers/factory.py` (`ParserFactory`)
  * `parsers/languages/python.py`, `javascript.py`, `cpp.py`, `java.py`, `go.py`, `rust.py`
  * `parsers/filter.py` (`extract_third_party_imports`)
* **What it does:**
  1. Generates a top-level `File` node for each file.
  2. Extracts third-party and standard library imports to filter out external symbols (e.g., `import requests`, `import numpy`).
  3. Walks the code (AST for Python; syntax-aware parsers for JS, C++, Java, Go, Rust) to extract definitions and reference call sites.
* **Input Data:**
  * `rel_path: str` (e.g., `"auth/service.py"`)
  * `content: str` (raw source code)
* **Output Data Structures:**
  * `defs: List[CodeNode]` (Definition sites: functions, methods, classes)
  * `refs: List[Tuple[CodeNode, Optional[str]]]` (Reference sites: function invocations, call sites, paired with their parent enclosing function ID)

```python
# CodeNode Data Structure Schema
CodeNode(
    node_id="auth/service.py:L24:def:validate_token",
    file="auth/service.py",
    line=24,
    name="validate_token",
    type="def",             # "def" (definition) or "ref" (call site)
    category="function",    # "file" | "class" | "function" | "method" | "call"
    snippet="def validate_token(token: str, tenant_id: str):"
)
```

---

### Phase 3: Dependency Graph Construction ($G = (V, E)$)
* **Responsible Module:** `graph/`
  * `graph/builder.py` (`RepoGraphBuilder`)
  * `graph/container_edges.py` (`add_containment_edge`)
  * `graph/invocation_edges.py` (`resolve_invocation_edges`)
* **What it does:**
  1. Adds all nodes ($V$) to a NetworkX directed graph.
  2. Creates **Containment Edges** ($E_{\text{contain}}$):
     * `File -> Class`
     * `File -> Function`
     * `Class -> Method`
     * `Function/Method -> Call Site (Ref)`
  3. Resolves **Invocation Edges** ($E_{\text{invoke}}$):
     * Matches `ref` call sites to corresponding internal `def` targets by symbol name, qualified name (`Class.method`), or namespace (`Class::method`).
* **Input Data:**
  * `file_nodes: Dict[str, CodeNode]`
  * `defs: List[CodeNode]`
  * `refs: List[Tuple[CodeNode, Optional[str]]]`
* **Output Data Structure:**
  * `graph: networkx.DiGraph` where:
    * **Nodes ($V$)**: Symbol definitions and call references with line numbers and snippet attributes.
    * **Edges ($E$)**: Directed relations with edge attributes:
      * `relation="contain"`: Lexical/structural containment.
      * `relation="invoke"`: Function/method invocation call path.

---

### Phase 4: Git Diff Parsing & Seed Node Identification
* **Responsible Module:** `traversal/seed_extractor.py` & `parsers/diff_parser.py`
* **What it does:**
  1. Parses unified diff headers to determine modified files and changed line ranges.
  2. Cross-references changed lines with nodes in the graph $G$ to isolate the modified symbols (functions, methods, classes).
* **Input Data:**
  * `graph: networkx.DiGraph`
  * `diff_text: str`
* **Output Data Structure:**
  * `seed_nodes: List[Dict[str, Any]]`
    * The initial set of changed nodes $S \subset V$ acting as starting points for graph traversal.
    * Example:
      ```python
      [
          {
              "node_id": "auth/service.py:L24:def:validate_token",
              "file": "auth/service.py",
              "line": 24,
              "name": "validate_token",
              "category": "function"
          }
      ]
      ```

---

### Phase 5: $k$-Hop Ego-Graph Traversal & Impact Analysis
* **Responsible Module:** `traversal/`
  * `traversal/ego_graph.py` (`extract_ego_graph`)
  * `traversal/impact_analyzer.py` (`analyze_impact_summary`)
* **What it does:**
  1. Traverses the graph outward from seed nodes $S$ up to $k$ hops (default $k=2$) along reverse invocation edges and containment edges.
  2. Extracts the minimal induced subgraph $G_{\text{ego}} = (V_{\text{ego}}, E_{\text{ego}})$ containing only reachable code dependencies.
  3. Groups nodes into structural categories (direct callers, indirect callers, callees, affected files).
* **Input Data:**
  * `graph: networkx.DiGraph`
  * `seed_nodes: List[Dict]`
  * `k: int` (Hop distance)
* **Output Data Structures:**
  1. `ego_graph: networkx.DiGraph`
     * Subgraph restricted to the affected neighborhood.
  2. `impact_summary: ImpactSummary` (Dataclass):
     * `seed_nodes: List[CodeNode]` (Directly edited functions)
     * `direct_callers: List[CodeNode]` (1-hop functions that directly call the modified code)
     * `indirect_callers: List[CodeNode]` (2-hop callers)
     * `callees: List[CodeNode]` (Functions called by the modified code)
     * `affected_files: List[str]` (Unique list of affected downstream files)
     * `total_ego_nodes: int`
     * `total_ego_edges: int`

---

### Phase 6: Graph-RAG Serialization & Prompt Synthesis
* **Responsible Module:** `rag/`
  * `rag/serializer.py` (`serialize_ego_graph`)
  * `rag/prompt_builder.py` (`build_impact_prompts`)
* **What it does:**
  1. Flattens the non-linear ego-graph into structured Markdown text representing the call hierarchy and affected lines.
  2. Injects the serialized graph context alongside the raw Git diff into an LLM prompt.
* **Input Data:**
  * `ego_graph: networkx.DiGraph`
  * `seed_nodes: List[Dict]`
  * `diff_text: str`
* **Output Data Structures:**
  * `graph_context: str`
    * Serialized text detailing:
      * Modified seed definitions with line numbers.
      * Call sites and caller functions.
      * Structural containment links.
  * `prompts: Dict[str, str]`
    * `prompts["system_prompt"]`: Software architect role instructions.
    * `prompts["user_prompt"]`: Injected Git diff + Graph topology + structured report schema.

---

### Phase 7: LLM Reasoning & Co-Change Recommendation
* **Responsible Module:** `llm/`
  * `llm/gemini_client.py` (`GeminiClient`)
  * `llm/mock_client.py` (`MockLLMClient` - deterministic fallback)
* **What it does:**
  * Sends the synthesized Graph-RAG prompt to Google Gemini API (or rule-based fallback).
  * The LLM maps the exact code changes in the diff to the downstream callers identified in the graph context and predicts what will break.
* **Input Data:**
  * `prompts: Dict[str, str]` (or `graph_context`, `diff_text`, `impact_summary`)
* **Output Data Structure:**
  * `report: str` (GitHub-flavored Markdown text)
    * **1. Summary of Change:** Detailed breakdown of modified signatures and logic.
    * **2. Affected Files & Lines:** Explicit line numbers and files impacted.
    * **3. Impact Rationale:** Why each file breaks (caller, mock mismatch, subclass).
    * **4. Recommended Co-Changes:** Concrete code adjustments required in caller files.
    * **5. Testing Requirements:** Tests requiring execution or new test assertions.

---

## 3. Data Structure Transformation Lifecycle Matrix

| Phase | Input Format | Transformation Engine | Output Data Structure | Output Type |
| :--- | :--- | :--- | :--- | :--- |
| **1. Ingest** | Repo Slug / Local Path | `GitHubClient` / `LocalLoader` | File map + unified diff | `Dict[str, str]`, `str` |
| **2. Parse** | File content string | Language AST / Regex Parsers | Symbol definitions & call references | `List[CodeNode]`, `List[Tuple]` |
| **3. Graph** | Parsed nodes | `RepoGraphBuilder` | Line & symbol dependency graph | `networkx.DiGraph` |
| **4. Diff** | DiGraph + Diff text | `extract_seed_nodes` | Modified symbol nodes ($S$) | `List[Dict[str, Any]]` |
| **5. Traversal**| Full DiGraph + $S$ + $k$ | `extract_ego_graph` + `analyze_impact_summary` | Subgraph + Structural metrics | `networkx.DiGraph`, `ImpactSummary` |
| **6. RAG** | Ego DiGraph + Diff | `serialize_ego_graph` + `build_impact_prompts` | Prompt context strings | `str`, `Dict[str, str]` |
| **7. LLM** | Prompt dictionary | `GeminiClient` (Google GenAI / REST) | Structured impact & co-change report | `str` (Markdown) |

---

## 4. Pipeline Execution Orchestration

In `main.py`, the entire flow runs sequentially:

```python
# 1. Ingest
loader = GitHubClient(...) if github_slug else LocalLoader(...)
file_contents = loader.load_all_files()
diff_text = loader.get_diff()

# 2 & 3. Parse & Build Graph
builder = RepoGraphBuilder()
graph = builder.build_from_files(file_contents)

# 4. Extract Seed Nodes from Diff
seed_nodes = extract_seed_nodes(graph, diff_text)

# 5. Extract k-hop Ego Subgraph & Summarize Impact
ego_graph = extract_ego_graph(graph, seed_nodes, k=k)
impact_summary = analyze_impact_summary(graph, ego_graph, seed_nodes)

# 6. Graph-RAG Serialization
graph_context = serialize_ego_graph(ego_graph, seed_nodes, diff_text)

# 7. LLM Co-Change Recommendations
llm_client = GeminiClient(model_name=model_name)
report = llm_client.generate_report(graph_context, diff_text, impact_summary)
```
