# Codelysis: Architecture & Workflows
## Visual Architecture Diagrams, Sequence Workflows, and Dataflow Specifications

---

## 1. High-Level System Architecture

Codelysis separates concerns across five distinct architectural layers:
1. **Source Ingestion Layer:** Zero-clone GitHub API or local filesystem reader.
2. **Language Parsing & AST/CST Engine:** Python AST, Tree-sitter CST, and regex fallback parsers.
3. **Graph Construction & Symbol Indexing Layer:** MultiDiGraph builder, 6-tier scoped symbol resolver, and typed edge generators.
4. **Traversal, Evolution & Causal Intelligence Layer:** Seed mapper, ego-subgraph extractor, weighted Personalized PageRank, Git co-change miner, path tracer, and error predictor.
5. **Presentation & Synthesis Layer:** Graph-RAG serializer, Google Gemini LLM reasoning, REST API server, and Next.js force-directed interactive canvas.

```mermaid
flowchart TD
    subgraph Layer1 ["Layer 1: Ingestion"]
        GH["GitHubClient\n(REST API, Zero-Clone)"]
        Local["LocalLoader\n(Local Filesystem)"]
        GitCli["Git CLI Engine\n(git log / git diff)"]
    end

    subgraph Layer2 ["Layer 2: Multi-Language Parsing"]
        Factory["ParserFactory"]
        PyParser["PythonParser\n(ast.NodeVisitor)"]
        TSParser["TreeSitterJavaScriptParser\n(CST Walker)"]
        JSRegex["JavaScriptParser\n(Regex Fallback)"]
        GenericParsers["Generic Parsers\n(Java, C++, Go, Rust, C#)"]
        DiffParser["DiffParser\n(Unified Diff Hunks)"]
        
        Factory --> PyParser
        Factory --> TSParser
        Factory --> JSRegex
        Factory --> GenericParsers
    end

    subgraph Layer3 ["Layer 3: MultiDiGraph & Symbol Registry"]
        SymIdx["SymbolIndex\n(6-Tier Scoped Resolution)"]
        Builder["RepoGraphBuilder\n(nx.MultiDiGraph G=(V,E))"]
        E_Contain["container_edges\n(E_contain)"]
        E_Import["import_edges\n(E_import)"]
        E_Inherit["inheritance_edges\n(E_inherit, E_override, E_implement)"]
        E_Invoke["invocation_edges\n(E_invoke, E_invoke_candidate)"]
        
        SymIdx --> Builder
        Builder --> E_Contain
        Builder --> E_Import
        Builder --> E_Inherit
        Builder --> E_Invoke
    end

    subgraph Layer4 ["Layer 4: Traversal & Evolution Intelligence"]
        SeedExt["SeedExtractor\n(Diff Line to AST Mapping)"]
        EgoExt["EgoGraphExtractor\n(k-Hop Bounded BFS)"]
        PPR["WeightedTraversal\n(Pure-Python PPR)"]
        GitMiner["GitCoChangeMiner\n(Jaccard Historical Coupling)"]
        PathTracer["PathTracer\n(Causal Evidence Paths)"]
        ErrorPred["ErrorPredictor\n(Signature-Diff Checker)"]
        TestImpact["TestImpactAnalyzer\n(Multi-Tier TIA Engine)"]
        Hybrid["HybridRetriever\n(Tri-Part Score Fusion)"]
        
        SeedExt --> EgoExt
        EgoExt --> PPR
        EgoExt --> PathTracer
        EgoExt --> ErrorPred
        EgoExt --> TestImpact
        GitMiner --> Hybrid
        PPR --> Hybrid
    end

    subgraph Layer5 ["Layer 5: Presentation & Synthesis"]
        Serializer["RAG Serializer\n(Hierarchical Context)"]
        Gemini["GeminiClient\n(google-genai / Rule Fallback)"]
        Server["server.py\n(Port 8000 REST API)"]
        Frontend["Next.js Dynamic Canvas\n(Port 3000 Force-Directed UI)"]
        
        Serializer --> Gemini
        Gemini --> Server
        Hybrid --> Server
        PathTracer --> Server
        ErrorPred --> Server
        Server --> Frontend
    end

    Layer1 --> Layer2
    Layer2 --> Layer3
    DiffParser --> SeedExt
    Layer3 --> Layer4
    Layer4 --> Layer5
```

---

## 2. Graph Schema & Typed Multigraph Representation

Codelysis represents repositories using `networkx.MultiDiGraph`. Two identical nodes can be connected by multiple parallel edges of distinct relationship types without overwriting each other.

```mermaid
graph LR
    subgraph FileNode ["File: auth/service.py"]
        direction TB
        ClassAuth["Class: AuthService"]
        FuncVal["Function: validate_token(token)"]
        FuncLogin["Function: login_user(token)"]
        RefSite["Ref: L14:C7 validate_token(token)"]
    end

    subgraph RemoteFile ["File: core/service.py"]
        direction TB
        ClassCore["Class: CoreProcessor"]
        FuncProcess["Function: process_request(token, data)"]
        RemoteRef["Ref: L6:C15 validate_token(token)"]
    end

    ClassAuth -- "E_contain" --> FuncVal
    ClassAuth -- "E_contain" --> FuncLogin
    FuncLogin -- "E_contain" --> RefSite
    
    RefSite -- "E_invoke (conf=1.0, intra_class)" --> FuncVal
    RemoteRef -- "E_invoke (conf=0.95, import_exact)" --> FuncVal
    
    ClassCore -- "E_contain" --> FuncProcess
    FuncProcess -- "E_contain" --> RemoteRef
    
    FileNode -- "E_import" --> RemoteFile
```

### 2.1 Node Data Model
```python
CodeNode(
    node_id="auth/service.py:L14:C7:ref:validate_token",
    file="auth/service.py",
    line=14,
    name="validate_token",
    type="ref",                         # "def" or "ref"
    category="call",                    # "class", "function", "method", "call", "file"
    end_line=14,
    start_col=7,
    end_col=21,
    qualified_name="auth.service.login_user.validate_token",
    signature="()",
    docstring="",
    parent_scope="login_user",
    snippet="    if not validate_token(token):",
    metadata={"receiver": None, "arg_count": 1, "kw_names": []}
)
```

### 2.2 Edge Data Model
Each edge in the `MultiDiGraph` is indexed by `(u, v, key, data)`:
- **`E_contain` Key:** `f"E_contain:{v}"`
- **`E_invoke` Key:** `f"E_invoke:{v}"`
- **`E_invoke_candidate` Key:** `f"E_invoke_candidate:{v}"`
- **`E_import` Key:** `f"E_import:{symbol}:{target_node_id}"`
- **`E_inherit` Key:** `f"E_inherit:{target_class_id}"`
- **`E_override` Key:** `f"E_override:{sub_class_id}:{sm.node_id}:{base_method.node_id}"`

---

## 3. Six-Tier Scoped Symbol Resolution Decision Tree

When resolving a call site `ref_node` to its target `def_node`, the `SymbolIndex` executes this deterministic decision hierarchy:

```mermaid
flowchart TD
    Start["Call Site: ref_node\n(name, from_file, scope, receiver)"] --> CheckReceiver{"Is receiver in\n('self', 'this', 'cls')?"}
    
    CheckReceiver -- Yes --> Tier1["Tier 1: Intra-Class Exact Match\nSearch enclosing class hierarchy:\nOuter.Inner -> Outer -> Base\nconf = 1.00"]
    Tier1 --> Found1{"Target found?"}
    Found1 -- Yes --> FinishConfirmed["Return Confirmed E_invoke"]
    Found1 -- No --> CheckImport
    
    CheckReceiver -- No --> CheckImport{"Is name in file's\nimport alias map?"}
    
    CheckImport -- Yes --> Tier2["Tier 2: Directly Imported Symbol\nMatch module + symbol\nconf = 0.95 / 0.90"]
    Tier2 --> Found2{"Target found?"}
    Found2 -- Yes --> FinishConfirmed
    Found2 -- No --> CheckModuleAttr
    
    CheckImport -- No --> CheckModuleAttr{"Is receiver an\nimported module alias?"}
    
    CheckModuleAttr -- Yes --> Tier3["Tier 3: Module-Attribute Receiver\nMatch mod.func() in target module\nconf = 0.90"]
    Tier3 --> Found3{"Target found?"}
    Found3 -- Yes --> FinishConfirmed
    Found3 -- No --> CheckLocal
    
    CheckModuleAttr -- No --> CheckLocal{"Does symbol exist in\nsame file / lexical scope?"}
    
    CheckLocal -- Yes --> Tier4["Tier 4: Lexical Scope & Local Def\nSearch enclosing function -> file\nconf = 0.95"]
    Tier4 --> Found4{"Target found?"}
    Found4 -- Yes --> FinishConfirmed
    Found4 -- No --> CheckSibling
    
    CheckLocal -- No --> CheckSibling{"Does symbol exist in\nsame directory package?"}
    
    CheckSibling -- Yes --> Tier5["Tier 5: Sibling Module\nMatch definitions in same directory\nconf = 0.70"]
    Tier5 --> Found5{"Target found?"}
    Found5 -- Yes --> FinishConfirmed
    Found5 -- No --> CheckRepoWide
    
    CheckSibling -- No --> CheckRepoWide{"Search entire repo\nfor short name"}
    
    CheckRepoWide --> CountCandidates{"Count matches\nacross repo"}
    CountCandidates -- "Count == 1" --> Tier6A["Tier 6A: Unique Repo Match\nconf = 0.50"] --> FinishConfirmed
    CountCandidates -- "Count > 1" --> Tier6B["Tier 6B: Ambiguous Symbol\nconf = 0.25"] --> FinishCandidate["Return E_invoke_candidate\n(Strictly isolated)"]
    CountCandidates -- "Count == 0" --> Unresolved["Unresolved Symbol\n(External library / stdlib)\nNo edge created"]
```

---

## 4. End-to-End Change Impact Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Developer
    participant Client as Next.js Web UI
    participant Server as server.py (Port 8000)
    participant Ingestion as LocalLoader / GitHubClient
    participant Builder as RepoGraphBuilder
    participant Extractor as SeedExtractor
    participant Ego as EgoGraphExtractor
    participant Traversal as WeightedTraversal (PPR)
    participant Tracer as PathTracer & ErrorPredictor
    participant Evolution as GitCoChangeMiner
    participant Hybrid as HybridRetriever
    participant LLM as GeminiClient / MockClient

    Developer->>Client: Submit repo path or diff
    Client->>Server: POST /api/analyze {repo_path, diff_text, k}
    Server->>Ingestion: load_all_files() & get_diff()
    Ingestion-->>Server: file_contents, diff_text
    
    Server->>Builder: build_from_files(file_contents)
    Note over Builder: Pass 1: Parse AST/CST & register SymbolIndex<br/>Pass 2: Wire E_contain<br/>Pass 3: Wire E_import<br/>Pass 4: Wire E_inherit & E_override<br/>Pass 5: Wire E_invoke via SymbolIndex
    Builder-->>Server: MultiDiGraph G = (V, E)
    
    Server->>Extractor: extract_seed_nodes(G, diff_text)
    Extractor-->>Server: seed_nodes: List[CodeNode]
    
    Server->>Ego: extract_ego_graph(G, seed_nodes, k=2)
    Note over Ego: Bidirectional BFS (exclude candidates by default)
    Ego-->>Server: Ego Subgraph G_ego
    
    par Parallel Analytical Intelligence
        Server->>Traversal: calculate_change_conditioned_ranking(G, seed_nodes)
        Traversal-->>Server: ranked_nodes: List[RankedImpactNode]
    and
        Server->>Tracer: trace_evidence_paths(G_ego, seed_nodes)
        Tracer-->>Server: evidence_paths: Dict[str, List[Path]]
    and
        Server->>Tracer: predict_potential_errors(G_ego, seed_nodes, diff_text)
        Tracer-->>Server: predicted_errors: List[Dict]
    and
        Server->>Evolution: get_co_changed_files(seed_files)
        Evolution-->>Server: git_co_changes: List[CoChangeRelation]
    and
        Server->>TestImpact: identify_relevant_tests(G, seed_nodes, git_co_changes)
        TestImpact-->>Server: test_recommendations: List[TestImpactRecommendation]
    end
    
    Server->>Hybrid: retrieve_hybrid_impact(G, seed_nodes, diff_text)
    Hybrid-->>Server: hybrid_rankings: List[HybridRetrievalResult]
    
    Server->>LLM: generate_report(serialized_ego_graph, diff_text)
    LLM-->>Server: markdown_report: str
    
    Server-->>Client: JSON Response (nodes, edges, rankings, errors, report)
    Client->>Developer: Render Interactive Dynamic Canvas & 5 Intelligence Tabs
```

---

## 5. Force-Directed Canvas Physics Architecture

The Next.js frontend (`frontend/components/GraphCanvas.jsx`) renders an interactive, physics-driven dependency graph using an HTML5 Canvas and a custom Euler-Verlet integration loop:

```mermaid
flowchart LR
    Init["Initial Coordinates\n(Random / Stable Grid)"] --> Loop["Animation Frame Loop\n(requestAnimationFrame)"]
    
    subgraph PhysicsEngine ["Physics Simulation Step"]
        Repulsion["Coulomb Repulsion\nF_rep = -k_rep / dist^2"]
        Spring["Hooke Spring Tension\nF_spring = k_spring * (dist - l_0)"]
        Center["Center Gravity Force\nF_grav = k_grav * (pos - center)"]
        Damping["Velocity Damping\nv = v * damping (0.85)"]
        
        Repulsion --> Spring
        Spring --> Center
        Center --> Damping
    end
    
    Loop --> PhysicsEngine
    PhysicsEngine --> UserInteraction{"User Event?"}
    
    UserInteraction -- "Mouse Drag" --> Pin["Update node.x, node.y\nSet node.pinned = true"]
    UserInteraction -- "Wheel Zoom" --> Zoom["Transform scale (0.2x - 3.0x)\nAdjust viewport pan"]
    UserInteraction -- "Node Hover" --> Hover["Trace Downstream Path\nHighlight connected nodes & edges\nDim unrelated nodes to 15% opacity"]
    UserInteraction -- "None" --> Render["Canvas draw:\n1. Edges (color, dash, particles)\n2. Nodes (glow, label, status badge)\n3. Tooltips"]
    
    Pin --> Render
    Zoom --> Render
    Hover --> Render
    Render --> Loop
```

### 5.1 Color Palette & Node Visual Semantics
- **Seed Node (`#ef4444` Red):** Directly modified definition in Git diff. Pulsing radial glow.
- **Direct Caller (`#f97316` Orange):** 1-hop confirmed caller (`E_invoke`).
- **Indirect Caller (`#eab308` Yellow):** 2-hop transitive caller.
- **Unit Test Harness (`#06b6d4` Cyan):** Caller residing in a test file (`tests/test_*.py`).
- **Callee (`#8b5cf6` Purple):** Outgoing dependency called by modified seed.
- **Normal Entity (`#1e293b` Dark Slate):** Contextual structural entity.

---

## 6. Layer-by-Layer Data Contract Specifications

| Layer | Input Data Structures | Processing Logic | Output Data Structures |
| :--- | :--- | :--- | :--- |
| **1. Ingestion** | GitHub slug / Local dir path | File tree traversal; git diff execution | `Dict[str, str]` (file contents), `diff_text: str` |
| **2. Parsing** | `(file_path, content_str)` | AST visitor / Tree-sitter CST traversal | `List[CodeNode]` (defs), `List[Tuple[CodeNode, Optional[str]]]` (refs) |
| **3. Graph Construction** | Definitions, references, imports | 6-tier `SymbolIndex` resolution; multi-edge insertion | `nx.MultiDiGraph G = (V, E)` |
| **4. Seed Extraction** | Unified diff string, Graph $G$ | Hunk header scanning; line-to-interval matching | `List[CodeNode]` (seed nodes $S \subseteq V$) |
| **5. Subgraph Extraction** | Graph $G$, Seed nodes $S$, $k$ hops | Breadth-first search excluding candidates | Induced subgraph `G_ego = G[V_ego]` |
| **6. Weighted Traversal** | Graph $G$, Seed nodes $S$ | Relationship-weighted Personalized PageRank | `List[RankedImpactNode]` (PPR scores, severity tiers) |
| **7. Error Prediction** | Diff text, Subgraph $G_{ego}$ | AST signature-diff parameter mismatch check | `List[Dict]` (predicted `TypeError`, `AttributeError`) |
| **8. Test Impact Analysis** | Graph $G$, Seeds $S$, Co-changes | Multi-tier test detection (Direct, Indirect, Co-change, Candidate) | `List[TestImpactRecommendation]` (prioritized test suites) |
| **9. Git Evolution** | Git repository path, seed files | Commit history parsing; Jaccard association mining | `List[CoChangeRelation]` (co-change counts, Jaccard scores) |
| **10. Hybrid Retrieval** | Graph $G$, Seeds $S$, Diff, Git history | 3-way score fusion (Graph + Git + Token) | `List[HybridRetrievalResult]` (calibrated scores) |
| **11. RAG Serialization** | Subgraph $G_{ego}$, Seeds $S$, Diff, Tests | Hierarchical markdown context formatting | Serialized context string (bounded $\le 8000$ chars) |
| **12. LLM Generation** | Serialized context, Diff, Prompts | Google Gemini API call / rule-based fallback | Structured markdown impact report with TIA section |
| **13. API Delivery** | HTTP POST `/api/analyze` payload | Pipeline orchestration (`main.py`) | JSON response containing graph, intelligence, tests, and report |

