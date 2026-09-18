# Graph-RAG Code Change Impact Analysis & Co-Change Recommender
## Project Architecture & Design Document

### 1. Executive Summary & Core Objective
When developers modify a function, class signature, or API logic in a codebase, indirect downstream dependencies often break silently across multiple files. Traditional vector-based RAG retrieves semantically similar text chunks but fails to map exact code execution paths, function callers, class hierarchies, and import dependencies.

Based on the **RepoGraph (ICLR 2025)** framework, this project builds a **Graph-RAG Impact Analyzer** that:
1. Constructs a **repository-wide line & symbol code graph** $G = (V, E)$ using Abstract Syntax Trees (AST).
2. Filters out standard library and 3rd-party dependencies to keep only internal project relations.
3. Extracts a **$k$-hop Ego-Graph** surrounding any modified line, function, or `git diff`.
4. Flattens the Ego-Graph into structured prompt context for an LLM (Graph RAG).
5. Predicts and ranks **all related files that must be updated or re-tested**, detailing the specific line numbers, callers, and required code edits.

---

## 2. Directory & Module Structure

```
code_impact_graph_rag/
├── README.md                    # Setup, usage guide, and mathematical formulation
├── config.py                    # Project configurations (k-hops, LLM model choice, file extensions)
├── graph_builder.py             # AST parsing & Line-level Repository Graph Construction (G = (V, E))
├── diff_parser.py               # Parses Git diffs to identify modified lines/symbols (Seed Nodes)
├── impact_analyzer.py           # Ego-graph extraction (k-hop traversal, caller/callee tracing)
├── graph_rag_engine.py          # Context flattener & LLM prompt synthesis
├── recommender.py               # Recommender engine interfacing with LLM to produce structured recommendations
└── demo.py                      # Runnable end-to-end demonstration on a sample multi-file repository
```

---

## 3. Core Architectural Components

```
                    ┌──────────────────────────────────────────────┐
                    │               Target Codebase                │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Graph Builder (graph_builder.py)                                                 │
│  - Parses AST using Tree-sitter / Python AST                                        │
│  - Node Types: Definition (def), Reference (ref), File                              │
│  - Edge Types: E_contain (File -> Class -> Def), E_invoke (Ref -> Def)               │
│  - Filter: Excludes stdlib (len, print) and third-party imports (numpy, requests)   │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 2. Change Identifier & Seed Node Extractor (diff_parser.py)                        │
│  - Takes changed code / Git diff                                                     │
│  - Maps changed line numbers & modified symbols to initial Seed Nodes (S ⊂ V)       │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 3. Subgraph Retriever (impact_analyzer.py)                                          │
│  - Traverses Graph G starting from Seed Nodes S                                     │
│  - Computes k-hop Ego Subgraph G_ego = (V_ego, E_ego)                               │
│  - Identifies direct callers, indirect callers, subclasses, and importer files      │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 4. Graph RAG Engine & LLM Recommender (graph_rag_engine.py & recommender.py)       │
│  - Flattens G_ego into structured text representation                               │
│  - Constructs LLM System & Task Prompt containing repo sub-graph + code diff       │
│  - Queries LLM (Gemini / GPT-4) for impact analysis                                 │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │       Output: Affected File Report           │
                    │ - File 1: core/service.py (Line 42)          │
                    │   Reason: Caller function process_auth()     │
                    │   Action Required: Pass new 'tenant_id' arg │
                    │ - File 2: tests/test_auth.py (Line 18)       │
                    │   Reason: Mock signature mismatch            │
                    └──────────────────────────────────────────────┘
```

---

## 4. Graph Schema Definition

### Nodes ($V$)
Each node represents a line or code entity with metadata:
* **`node_id`**: String identifier (e.g. `auth/service.py:L24:def:validate_token`)
* **`file`**: File relative path (`auth/service.py`)
* **`line`**: Integer line number (`24`)
* **`name`**: Symbol identifier (`validate_token`)
* **`type`**: `def` (definition site) or `ref` (reference / invocation site)
* **`category`**: `function`, `class`, `method`, or `call`
* **`snippet`**: Source code line string

### Edges ($E$)
* **`E_contain`** (Structural Containment): Connects a container definition to its internal lines/children (e.g., `Class User` $\rightarrow$ `method login()`).
* **`E_invoke`** (Invocation / Dependency): Connects a reference call site (`ref`) to the target definition site (`def`).

---

## 5. Implementation Phases

| Phase | Description | Key Deliverables |
| :--- | :--- | :--- |
| **Phase 1: Graph Construction** | AST traversal, symbol indexing, stdlib filtering. | `graph_builder.py` |
| **Phase 2: Change Identification** | Git diff parsing, line-to-symbol mapping. | `diff_parser.py` |
| **Phase 3: Subgraph Extraction** | $k$-hop Ego-graph extraction, dependency tracing. | `impact_analyzer.py` |
| **Phase 4: Graph RAG Engine** | Subgraph serialization, LLM prompt engineering. | `graph_rag_engine.py` |
| **Phase 5: Evaluation & CLI** | End-to-end execution script & markdown report output. | `demo.py`, `recommender.py` |

---

## 6. Verification Plan

### Automated Verification
1. **Graph Accuracy Verification**: Run AST graph builder on test repository and verify node/edge count against expected call graph.
2. **Ego Subgraph Test**: Verify that modifying a utility function correctly identifies all 1-hop and 2-hop caller files.
3. **End-to-End Simulation**: Run `demo.py` to test full Graph RAG output against a multi-file Python codebase.

### Manual Verification
- Review the generated affected files report to ensure zero false negatives on critical call sites.
