# Codelysis: Master Documentation Index
## Complete Technical, Academic, Architectural, and Experimental Reference Hub

---

### Welcome to the Codelysis Documentation Suite

**Codelysis** is an advanced software engineering research and developer intelligence system extending the **RepoGraph (ICLR 2025)** framework. It combines repository-level Code Property Multigraphs ($\text{MultiDiGraph}$), relationship-weighted Personalized PageRank, six-tier scoped symbol resolution, historical Git co-change mining, causal error prediction, and an interactive dynamic Next.js visualization canvas.

This directory (`docs/`) contains the complete documentation suite for the project, structured for academic submission, evaluation, peer review, and future engineering expansion.

---

## 1. Documentation Map & Navigation

```text
docs/
├── README_Documentation_Index.md                <-- You are here
├── Codelysis_Complete_Technical_Documentation.md <-- Full system manual & code reference
├── Codelysis_Academic_Project_Report.md         <-- Formal university/conference paper
├── Codelysis_Architecture_and_Workflows.md      <-- Visual diagrams, sequence charts & schemas
├── Codelysis_Development_Status_and_Roadmap.md  <-- Component audit, debt, tests & roadmap
└── Codelysis_Research_and_Evaluation_Plan.md    <-- Hypotheses, baselines, metrics & ablation
```

### Document Directory & Descriptions

| Document | Primary Audience | Core Contents |
| :--- | :--- | :--- |
| [**Codelysis Complete Technical Documentation**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Complete_Technical_Documentation.md) | Software Engineers & System Architects | Exhaustive technical reference covering every file, function, class, data model, parser, graph constructor, traversal engine, and API endpoint in the repository. |
| [**Codelysis Academic Project Report**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Academic_Project_Report.md) | Academic Evaluators & Researchers | Formal university-level research paper format: Abstract, Introduction, Mathematical Foundations, Methodology, Experimental Evaluation, Case Studies, and References. |
| [**Codelysis Architecture and Workflows**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Architecture_and_Workflows.md) | System Designers & Visual Learners | Mermaid architecture diagrams, graph schemas, end-to-end sequence charts, 6-tier symbol resolution decision trees, and Canvas physics documentation. |
| [**Codelysis Development Status and Roadmap**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Development_Status_and_Roadmap.md) | Project Managers & Contributors | Comprehensive component audit table, verified capabilities, technical debt, sprint timeline history, and phased 2027 future roadmap. |
| [**Codelysis Research and Evaluation Plan**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Research_and_Evaluation_Plan.md) | Empirical Researchers & Data Scientists | Scientific hypotheses (H1–H4), comparative baselines (BM25, Vector RAG, RepoGraph), temporal train/test split protocol, evaluation metrics, and ablation matrices. |

---

## 2. Reading Guides by Role

### For Academic Evaluators & Project Examiners
1. Start with the [**Academic Project Report**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Academic_Project_Report.md) for the theoretical problem formulation, mathematical models, and benchmark results.
2. Review the [**Research & Evaluation Plan**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Research_and_Evaluation_Plan.md) to inspect the ablation study design and methodology used to prevent historical data leakage.
3. Inspect Section 6 of the [**Complete Technical Documentation**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Complete_Technical_Documentation.md) to verify exact test execution counts and reproducible benchmark tables.

### For Software Architects & Developers
1. Start with [**Architecture & Workflows**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Architecture_and_Workflows.md) to visualize the 5-layer system pipeline and data flow.
2. Read the [**Complete Technical Documentation**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Complete_Technical_Documentation.md) for module-by-module implementation details, data models (`CodeNode`, `ImpactSummary`), and edge keying logic.
3. Consult the [**Development Status & Roadmap**](file:///Users/mac/Desktop/Codelysis/docs/Codelysis_Development_Status_and_Roadmap.md) for known limitations and planned milestones.

---

## 3. Quick Start & Verification Commands

All commands should be executed from the project root directory (`/Users/mac/Desktop/Codelysis`):

### 3.1 Run the Full Test Suite
Executes all 57 unit and regression tests across parsers, graph builder, symbol resolution, traversal, Git co-change mining, and Test Impact Analysis:
```bash
./venv/bin/python3 -m unittest discover tests -v
```
*Expected Result: 57 tests executed, 57 passed in ~0.40 seconds.*

### 3.2 Run the Scientific Evaluation Benchmark
Generates comparative retrieval accuracy, graph efficiency, 5-stage ablation, and Test Impact Analysis tables:
```bash
./venv/bin/python3 tests/evaluate_benchmark.py
# Or generate machine-readable JSON:
./venv/bin/python3 tests/evaluate_benchmark.py --json benchmark_results.json
```
*Expected Result: Live printouts of Table 1 (Downstream Caller Retrieval Accuracy), Table 2 (Graph Stats & Traversal Efficiency), Table 3 (5-Stage Ablation Matrix), and Table 4 (Test Impact Analysis Validation).*

### 3.3 Run the End-to-End Local Demo
Runs a deterministic, offline-capable verification pipeline demonstrating graph construction, seed extraction, weighted traversal, error prediction, test impact analysis, and report generation:
```bash
./venv/bin/python3 demo.py
```

### 3.4 Launch the Full-Stack Application
The system operates as a decoupled Python REST API backend and Next.js frontend:

```bash
# Terminal 1: Backend Server (Port 8000)
./venv/bin/python3 server.py

# Terminal 2: Next.js Frontend Dashboard (Port 3000)
cd frontend && npm run dev
```

Open your browser at `http://localhost:3000` to interact with:
- The force-directed graph canvas (movable nodes, downstream hover tracing).
- Impact ranking with severity badges.
- Predicted runtime and signature-diff errors.
- Test Impact Analysis tab with categorized test suites and execution commands.
- Historical Git co-change relationships.
- Multi-hop causal evidence paths.
- Actionable developer review checklist.

