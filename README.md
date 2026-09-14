# Graph-RAG Code Change Impact Analysis & Co-Change Recommender

> **Project Architecture & Academic Reference**: Based on the **RepoGraph (ICLR 2025)** framework for repository-wide code graph construction and Graph-RAG change impact analysis. Supports **Multi-Language Repositories** (Python, JavaScript, TypeScript, Java, C/C++, Go).

When developers modify a function signature, class hierarchy, or core API logic in a codebase, downstream dependencies across multiple files often break silently. Traditional vector-based RAG retrieves semantically similar text chunks but fails to trace explicit execution paths, call graphs, or containment structures.

This project implements a **Graph-RAG Code Impact Analyzer & Co-Change Recommender** that:
1. Constructs a repository-wide line & symbol directed dependency graph $G = (V, E)$ for multi-language codebases (`.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.cpp`, `.c`, `.h`, `.hpp`, `.go`).
2. Filters out standard library and third-party dependencies to isolate internal project relations.
3. Parses Git diffs to map modified lines/symbols to **Seed Nodes** $S \subseteq V$.
4. Extracts a **$k$-hop Ego Subgraph** $G_{ego}$ surrounding modified code.
5. Flattens $G_{ego}$ into structured prompt context for an LLM (Graph-RAG).
6. Generates a ranked Markdown impact report detailing affected files, line numbers, reason for impact, and required co-changes.

---

## Supported File Extensions & Languages

| Language | Supported Extensions | Symbol & Call Parsing |
| :--- | :--- | :--- |
| **Python** | `.py` | AST Visitor (`ast`) & pattern fallback |
| **JavaScript / TypeScript** | `.js`, `.jsx`, `.ts`, `.tsx` | Classes, functions, arrow functions, calls |
| **Java** | `.java` | Classes, interfaces, methods, calls |
| **C / C++** | `.c`, `.cpp`, `.h`, `.hpp` | Classes, structs, functions, calls |
| **Go** | `.go` | Structs, interfaces, funcs, receiver methods, calls |

---

## Directory & Module Structure

```text
code_impact_graph_rag/
│
├── README.md               # Setup, usage guide, & multi-language documentation
├── config.py               # Configurations (k-hops, extensions, model choice, stdlib filters)
│
├── graph_builder.py        # Multi-language AST & symbol dependency graph builder G = (V, E)
├── diff_parser.py          # Unified Git diff parser & Seed Node extractor S ⊂ V
├── impact_analyzer.py      # k-hop Ego Subgraph G_ego retrieval & caller/callee tracing
├── graph_rag_engine.py     # Graph-RAG flattener & structured LLM context synthesizer
├── recommender.py          # LLM interface (Gemini / OpenAI with rule-based fallback)
│
├── demo.py                 # End-to-end CLI demonstration script
│
├── sample_repo/            # Multi-file test codebase
│   ├── auth/ (service.py, token.py)
│   ├── core/ (service.py)
│   ├── models/ (user.py)
│   └── tests/ (test_auth.py)
│
└── tests/                  # Automated unit test suite
    ├── test_graph_builder.py
    ├── test_diff_parser.py
    └── test_impact_analyzer.py
```

---

## Graph Schema Definition

### Nodes ($V$)
Each node represents a line or code entity with metadata:
- `node_id`: String identifier (e.g. `auth/service.py:L3:def:validate_token`)
- `file`: Relative file path (`auth/service.py`)
- `line`: Integer line number (`3`)
- `name`: Symbol identifier (`validate_token`)
- `type`: `def` (definition site) or `ref` (reference / call site)
- `category`: `file`, `class`, `function`, `method`, or `call`
- `snippet`: Source code line string

### Edges ($E$)
- `E_contain` (Structural Containment): Connects container to internal definitions or call sites (e.g., File $\to$ Function, Class $\to$ Method).
- `E_invoke` (Invocation Dependency): Connects call reference site (`ref`) to target definition site (`def`).

---

## Quick Start & Setup

### 1. Requirements
- Python 3.10+
- `networkx`
- Optional: `google-genai` (for Gemini API calls) or `openai` (for OpenAI GPT-4 API calls)

### 2. Installation
```bash
pip install networkx google-genai python-dotenv
```

---

## Execution Guide

### Run on Any Repository (Python, JS/TS, Java, C/C++, Go)
```bash
python code_impact_graph_rag/demo.py --repo "/path/to/any/repository"
```

### Options
- `--repo`: Path to target repository directory (default: `code_impact_graph_rag/sample_repo`).
- `--k`: Number of graph hops for ego subgraph extraction (default: `2`).
- `--diff`: Unified diff text string or Git diff comparison.
- `--output`: Filepath to save the generated Markdown report.

---

## Running Unit Tests

Run the multi-language test suite via `unittest`:
```bash
python -m unittest discover -s code_impact_graph_rag/tests -v
```
