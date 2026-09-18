# Codelysis: Multi-Language RepoGraph Impact Analysis & Co-Change Recommender

> **Academic Foundation**: Based on the **RepoGraph (ICLR 2025)** framework for repository-wide line-level code graph construction and Graph-RAG change impact analysis. Supports **Multi-Language Repositories** (Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, C#, and Universal fallback).

When developers modify a function signature, class hierarchy, or core API logic in a codebase, downstream dependencies across multiple files often break silently. Traditional vector-based RAG retrieves semantically similar text chunks but fails to trace explicit execution paths, call graphs, or containment structures.

**Codelysis** implements a **Graph-RAG Code Impact Analyzer & Co-Change Recommender** that:
1. Constructs a repository-wide line & symbol directed dependency graph $G = (V, E)$ for multi-language codebases (`.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.cpp`, `.c`, `.h`, `.hpp`, `.go`, `.rs`, `.cs`).
2. Filters out standard library and third-party dependencies to isolate internal project relations (RepoGraph Section 3.1 Step 2).
3. Parses Git diffs (or GitHub PR diffs) to map modified lines/symbols to **Seed Nodes** $S \subseteq V$.
4. Extracts a **$k$-hop Ego Subgraph** $G_{ego}$ surrounding modified code (RepoGraph Section 3.2).
5. Flattens $G_{ego}$ into structured prompt context for an LLM (Graph-RAG).
6. Connects to **Google Gemini API** (or offline rule-based fallback) to generate a ranked Markdown impact report detailing affected files, line numbers, reason for impact, and required co-changes.
7. Supports **Zero-Clone GitHub API** analysis directly from public or private GitHub repositories.

---

## Supported File Extensions & Languages

| Language | Supported Extensions | Symbol & Call Parsing |
| :--- | :--- | :--- |
| **Python** | `.py` | AST Visitor (`ast`) & pattern fallback |
| **JavaScript / TypeScript** | `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs` | ES6 classes, functions, arrow functions, methods, calls |
| **Java / Kotlin** | `.java`, `.kt` | Classes, interfaces, methods, calls |
| **C / C++** | `.c`, `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp` | Classes, structs, functions, methods, calls |
| **Go** | `.go` | Structs, interfaces, funcs, receiver methods, calls |
| **Rust** | `.rs` | Structs, enums, impl blocks, fns, calls |
| **C#** | `.cs` | Classes, interfaces, methods, calls |
| **Universal Fallback** | Any code file | Class, function, and call pattern matcher |

---

## Directory & Modular Architecture

The codebase is decoupled into task-segregated, single-responsibility modules:

```text
Codelysis/
├── config.py                     # Central configuration constants & defaults
├── main.py                       # Unified CLI runner (supports GitHub API & local repo)
├── demo.py                       # Backwards-compatible wrapper pointing to main.py
│
├── core/                         # Core domain models & types
│   ├── types.py                  # CodeNode, NodeType ('def'/'ref'), Category, EdgeType
│   └── models.py                 # DiffChange, SeedNode, ImpactSummary, CoChangeReport
│
├── parsers/                      # Parsing system
│   ├── base.py                   # BaseParser abstract interface
│   ├── factory.py                # ParserFactory: maps file extension to language parser
│   ├── filter.py                 # Multi-language Built-in & 3rd-party relation filtering
│   ├── diff_parser.py            # Unified git diff parser (maps changed lines per file)
│   └── languages/                # Dedicated per-language AST & pattern parsers
│       ├── python.py             # Python AST visitor
│       ├── javascript.py         # JS/TS parser
│       ├── java.py               # Java/Kotlin parser
│       ├── cpp.py                # C/C++ parser
│       ├── golang.py             # Go parser
│       ├── rust.py               # Rust parser
│       ├── csharp.py             # C# parser
│       └── generic.py            # Universal fallback parser
│
├── graph/                        # RepoGraph Construction (G = (V, E))
│   ├── builder.py                # High-level coordinator (files -> nodes -> edges)
│   ├── container_edges.py        # Constructs E_contain edges (File -> Class -> Method -> Call)
│   └── invocation_edges.py       # Resolves E_invoke edges (ref call -> def symbol lookup)
│
├── traversal/                    # Subgraph Retrieval & Impact Analysis
│   ├── seed_extractor.py         # Maps diff changed lines to Seed Nodes (S ⊂ V)
│   ├── ego_graph.py              # Bidirectional k-hop ego subgraph extractor (RepoGraph Sec 3.2)
│   └── impact_analyzer.py        # Classifies direct callers (1-hop), indirect callers (2-hop), callees
│
├── rag/                          # Context Serialization & Prompt Engineering
│   ├── serializer.py             # Flattens ego subgraph into structured context (RepoGraph Fig 9)
│   └── prompt_builder.py         # RepoGraph prompt template construction
│
├── sources/                      # Code & Diff Ingestion (GitHub API & Local)
│   ├── base.py                   # BaseSourceLoader interface
│   ├── github_client.py          # GitHub REST API (trees, raw file blobs, PR/commit diff)
│   └── local_loader.py           # Local filesystem scanner & file reader
│
├── llm/                          # LLM Integration
│   ├── base.py                   # BaseLLMClient interface
│   ├── gemini_client.py          # Google Gemini API integration (REST + SDK fallback)
│   └── mock_client.py            # Deterministic rule-based fallback report generator
│
└── tests/                        # Modular Unit Tests
    ├── test_diff_parser.py       # Git diff hunk parsing tests
    ├── test_graph_builder.py     # Graph construction & edge wiring tests
    ├── test_impact_analyzer.py   # Traversal & caller classification tests
    ├── test_multilang_parsers.py # JS/TS, Java, Go, C++, Rust, C# parsing tests
    ├── test_sources.py           # Local loader & GitHub REST client tests
    └── test_llm.py               # Gemini client & offline mock tests
```

---

## Quick Start & Usage

### 1. Requirements
- Python 3.10+
- `networkx`
- `requests`

```bash
pip install networkx requests
```

### 2. Run on Local Repository
```bash
# Analyze local sample repository:
python3 main.py --repo sample_repo

# Analyze local repository with specific diff:
python3 main.py --repo /path/to/my/project --diff path/to/patch.diff --k 2
```

### 3. Run Directly on GitHub (Zero-Clone via GitHub API)
```bash
# Analyze a public repository:
python3 main.py --github owner/repo

# Analyze a specific Pull Request:
python3 main.py --github owner/repo --pr 42

# Optional: Set GITHUB_TOKEN to bypass rate limits
export GITHUB_TOKEN="your_token_here"
```

### 4. Enable Google Gemini API
Set your Gemini API key in your environment:
```bash
export GEMINI_API_KEY="your_gemini_api_key"
python3 main.py --repo sample_repo --model gemini-2.5-flash
```
*Note: If no API key is present, Codelysis automatically runs in offline mode using the deterministic rule-based generator.*

---

## Running Unit Tests

Run the complete test suite with `unittest`:
```bash
python3 -m unittest discover -s tests -v
```
