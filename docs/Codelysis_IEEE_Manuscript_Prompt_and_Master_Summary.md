# Codelysis: Master LLM Prompt & Project Summary for IEEE Manuscript Generation

> **How to Use This Document:**  
> Copy and paste the entire prompt block below into any frontier LLM (e.g., Claude 3.5 Sonnet, GPT-4o, or Google Gemini 1.5 Pro). It provides the complete context, rigorous mathematical equations, verified empirical benchmark data, and structural instructions required to generate an IEEE-format research paper or manuscript.

---

```markdown
# SYSTEM INSTRUCTION: IEEE TRANSACTIONS / CONFERENCE MANUSCRIPT WRITER

Act as a Principal Software Engineering Researcher, Graph-RAG Specialist, and IEEE Senior Member. Your task is to write a comprehensive, publication-ready research manuscript in IEEE format (or two-column IEEE LaTeX template format) titled:

**"Codelysis: Multi-Language Repository-Level Code Property Multigraph and Graph-RAG for Change Impact Analysis, Test Selection, and Software Evolution Intelligence"**

**Authors:**
- Naman Sanotiya (202451114@iiitvadodara.ac.in), Indian Institute of Information Technology Vadodara
- Tarun Jain (202451160@iiitvadodara.ac.in), Indian Institute of Information Technology Vadodara

---

## 1. RESEARCH MOTIVATION & PROBLEM STATEMENT
Modifying core function signatures, class interfaces, or module behaviors in large software repositories introduces subtle breaking regressions across distant downstream files. Traditional Vector Retrieval-Augmented Generation (RAG) and BM25 lexical search rely on textual similarity and are blind to:
1. Syntax-level call hierarchies and execution paths.
2. Object-oriented inheritance and method overrides.
3. Import bindings, module aliases, and variable lexical scopes.
4. Implicit, non-syntactic dependencies (e.g., config-to-code couplings) discoverable only through historical software evolution.

While **RepoGraph (ICLR 2025 by Ouyang et al.)** established the utility of line-level directed code graphs ($E_{contain}, E_{invoke}$) for LLM agents, it suffered from:
- A single unweighted directed graph model (`nx.DiGraph`) unable to hold multiple parallel typed relationships between the same pair of entities.
- Unweighted bidirectional BFS exploration that treats high-confidence direct callers and speculative cross-file matches identically.
- Node ID collisions when multiple invocations occur on the same line.
- Naive global short-name symbol resolution causing false-positive invocation edges.
- Absence of historical evolution mining (Git co-changes).
- Absence of Test Impact Analysis (TIA) for prioritizing affected unit tests.

**Codelysis** directly addresses these foundational limitations as an advanced research and engineering extension.

---

## 2. MATHEMATICAL FOUNDATIONS & METHODOLOGY

### A. Line-Level Code Property Multigraph $G = (V, E)$
Codelysis models repositories as a typed directed multigraph $G = (V, E, \Phi_V, \Phi_E)$ using `networkx.MultiDiGraph`.

#### 1) Collision-Free Node Representation:
Every node $v \in V$ is an atomic syntactic entity represented by:
$$v = \langle id, file, line_{start}, line_{end}, col_{start}, col_{end}, name, \tau, \gamma, \sigma, \rho \rangle$$
where:
- $id \in \Sigma^*$ is a deterministic collision-free key: `file:L<line>:C<col>:<category>:<name>`
- $\tau \in \{def, ref\}$ (definition vs reference/call site)
- $\gamma \in \{file, class, struct, func, method, call, import\}$
- $\sigma \in \Sigma^*$ is the source snippet
- $\rho \in \Sigma^*$ is the fully qualified lexical scope (e.g., `pkg.module.ClassName.method_name.<locals>.helper`)

#### 2) Typed Edge Multigraph ($E$):
Parallel edges connect identical node pairs with distinct keys and weights:
$$E = E_{contain} \cup E_{invoke} \cup E_{import} \cup E_{inherit} \cup E_{override} \cup E_{candidate}$$
- **$E_{contain}$ ($container \to member$, $w = 1.00$):** Hierarchical lexical containment.
- **$E_{invoke}$ ($ref \to def$, $w \in [0.50, 1.00]$):** Call-site to target definition (strictly preserving the RepoGraph ICLR 2025 edge convention).
- **$E_{import}$ ($file \to target\_file/symbol$, $w = 0.85$):** Module imports and aliases.
- **$E_{inherit}$ ($subclass \to superclass$, $w = 0.90$):** Class inheritance.
- **$E_{override}$ ($sub\_method \to base\_method$, $w = 0.95$):** Method overriding verified against ancestor signatures.
- **$E_{candidate}$ ($ref \to def$, $w = 0.25$):** Ambiguous repo-wide candidates (quarantined from confirmed dependency graphs).

### B. 6-Tier Scoped Symbol Resolution Protocol
To resolve an invocation $r$ to target definition $d$, the `SymbolIndex` executes a deterministic 6-tier fallback:
1. **Tier 1: Local Lexical Scope ($w = 1.00$):** Target exists in same block/function.
2. **Tier 2: Class Hierarchy Scope ($w = 0.95$):** Target exists in enclosing class or inherited base classes.
3. **Tier 3: Explicit Import Bindings ($w = 0.90$):** Target imported via `from X import Y` or aliased via `as Z`.
4. **Tier 4: File Module Scope ($w = 0.85$):** Target declared at file level.
5. **Tier 5: Sibling Package Scope ($w = 0.70$):** Target defined in same directory package.
6. **Tier 6: Repository-Wide Scope:**
   - If $|\text{matches}| = 1 \implies$ Confirmed $E_{invoke}$ ($w = 0.50$).
   - If $|\text{matches}| > 1 \implies$ Ambiguous Candidate $E_{candidate}$ ($w = 0.25$). Strictly isolated!

### C. Relationship-Weighted Personalized PageRank (RWR)
For seed nodes $S \subseteq V$ extracted from Git diff $\Delta$, impact distribution is computed via Personalized PageRank:
$$\mathbf{p}^{(t+1)} = (1 - c) \mathbf{W}_{norm}^\top \mathbf{p}^{(t)} + c \mathbf{s}$$
where $c = 0.15$ is restart probability, $\mathbf{W}_{norm}$ is the out-degree normalized edge weight transition matrix, and $\mathbf{s}$ is the seed teleport vector:
$$\mathbf{s}_v = \begin{cases} \frac{1}{|S|}, & v \in S \\ 0, & v \notin S \end{cases}$$

### D. Logarithmic Shortest Path Cost Inversion
To trace the strongest causal evidence path $\mathcal{P} = (v_0, v_1, \dots, v_k)$ maximizing multiplicative confidence $\prod_{i} w(v_i, v_{i+1})$, edge weights are transformed to positive additive costs:
$$\text{cost}(u, v) = -\ln(\max(10^{-4}, \min(1.0, w(u, v))))$$
Executing Dijkstra's algorithm on additive cost $\sum \text{cost}(e_i)$ guarantees selection of the path with maximum evidence strength:
$$\arg\min_{\mathcal{P}} \sum_{e \in \mathcal{P}} -\ln(w(e)) \equiv \arg\max_{\mathcal{P}} \prod_{e \in \mathcal{P}} w(e)$$

### E. Software Evolution Mining (Historical Git Co-Change)
Mines historical couplings using Jaccard association:
$$Jaccard(f_A, f_B) = \frac{|C(f_A) \cap C(f_B)|}{|C(f_A) \cup C(f_B)|}$$
**Temporal Leakage Elimination:** For evaluation commit $C_{eval}$ at timestamp $T$, mining is strictly bounded to $t_{commit} < T$, preventing future commit data leakage.

### F. Tri-Part Hybrid Retrieval & Score Fusion
For every candidate entity $v \in V_{ego}$, hybrid impact score is calibrated via:
$$S_{hybrid}(v) = \alpha \cdot S_{PPR}(v) + \beta \cdot S_{Git}(v) + \gamma \cdot S_{Lexical}(v)$$
with normalized weights $\alpha = 0.50, \beta = 0.30, \gamma = 0.20$ ($\alpha + \beta + \gamma = 1.00$).

### G. Multi-Tier Test Impact Analysis (TIA)
Prioritizes verification test suites across 4 rigorous tiers:
1. **Directly Related ($w = 0.85$):** Test AST explicitly invokes modified definition.
2. **Indirectly Related ($w = 0.65$):** Test reachable within $\le 2$ hops in the ego-graph.
3. **Historically Associated ($w = 0.55$):** Test file coupled via Git history ($Jaccard \ge 0.20$).
4. **Candidate Review ($w = 0.40$):** Test touches ambiguous candidate symbol.

---

## 3. EMPIRICAL BENCHMARK RESULTS (VERIFIED LIVE DATA)

### TABLE I: Graph Construction and Traversal Statistics
| Repository | Language | LOC | Nodes $(\|V\|)$ | Edges $(\|E\|)$ | Invocations | Build Time |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **sample_repo** | Python | 450 | 32 | 44 | 8 | **0.0027 s** |
| **bottlepy/bottle** | Python | 4,500 | 642 | 1,489 | 384 | **1.28 s** |
| **pallets/flask** | Python | 12,000 | 814 | 2,106 | 592 | **1.84 s** |

### TABLE II: Downstream Impact Retrieval Accuracy (Seed: `validate_token`)
| Retrieval Method | Recall@10 | Precision@10 | F1@10 | MRR | nDCG@10 | Context Tokens |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BM25 Lexical Search** | 100.0% | 50.0% | 66.7% | 0.500 | 66.5% | 1,420 |
| **Vector RAG (all-MiniLM-L6-v2)** | 66.7% | 20.0% | 30.8% | 1.000 | 65.1% | 2,850 |
| **RepoGraph (ICLR 2025 Baseline)** | 100.0% | 100.0% | 100.0% | 1.000 | 100.0% | 336 |
| **Codelysis (Weighted PPR)** | 100.0% | 30.0% | 46.1% | 0.500 | 73.3% | 450 |
| **Codelysis (Full Hybrid Fusion)**| 100.0% | 30.0% | 46.1% | 0.500 | 73.3% | 450 |

### TABLE III: 5-Stage Scientific Ablation Matrix
| Configuration | MultiDiGraph | Scoped SymbolIndex | Weighted PPR | Git Co-Change | Token Lexical | Recall@10 | F1@10 | MRR | nDCG@10 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. RepoGraph Baseline** | $\times$ | $\times$ | $\times$ | $\times$ | $\times$ | 100.0% | 100.0% | 1.000 | 100.0% |
| **2. Codelysis w/o Traversal** | $\checkmark$ | $\checkmark$ | $\times$ | $\times$ | $\times$ | 100.0% | 46.1% | 1.000 | 100.0% |
| **3. Codelysis w/o Git** | $\checkmark$ | $\checkmark$ | $\checkmark$ | $\times$ | $\times$ | 100.0% | 46.1% | 0.500 | 73.3% |
| **4. Codelysis w/o TIA** | $\checkmark$ | $\checkmark$ | $\checkmark$ | $\checkmark$ | $\times$ | 100.0% | 46.1% | 0.500 | 73.3% |
| **5. Full Codelysis System** | $\checkmark$ | $\checkmark$ | $\checkmark$ | $\checkmark$ | $\checkmark$ | **100.0%** | **46.1%** | **0.500** | **73.3%** |

### TABLE IV: Test Impact Analysis (TIA) Validation Benchmark
| Test Selection Strategy | Selected Tests / Total | Precision (%) | Recall (%) | Suite Reduction (%) | MRR |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **All Tests (Naive Execution)** | 8 / 8 | 25.0% | 100.0% | 0.0% | 0.500 |
| **Keyword/Path Matcher** | 3 / 8 | 66.7% | 50.0% | 62.5% | 0.500 |
| **RepoGraph Unweighted BFS** | 4 / 8 | 50.0% | 75.0% | 50.0% | 0.750 |
| **Codelysis Multi-Tier TIA** | **2 / 8** | **100.0%** | **100.0%** | **75.0%** | **1.000** |

---

## 4. CASE STUDY: BOTTLE PR #1541
In Pull Request #1541 on `bottlepy/bottle`, JSON serialization hooks were modified. Codelysis:
- Identified 10 direct invocation sites in `bottle.py` calling `JSONPlugin` and `apply` at lines 527, 964, 969, and 1015 in 14.2 seconds.
- Identified 2 critical unit tests in `test/test_outputfilter.py` requiring header updates from `application/json` to custom dumpers.
- Detected 2 indirect 2-hop downstream wrapper methods.
- BM25 and Vector RAG missed lines 964 and 1015 due to zero lexical overlap with `dump_func`.

---

## 5. REQUIRED IEEE PAPER STRUCTURE TO GENERATE
Write the complete paper following standard IEEE Transactions / Conference guidelines:
- **Title, Authors & Affiliations**
- **Abstract** (concise, quantitative, 200 words) & **Index Terms**
- **I. Introduction:** Motivation, RepoGraph context, limitations of prior work, 5 core contributions.
- **II. Related Work:** Code Property Graphs, Graph-RAG, Change Impact Analysis, Software Evolution Mining.
- **III. Code Property Multigraph Formulation:** Formal definitions of $V$ and $E$, MultiDiGraph semantics, collision-free keys, Tree-sitter CST parsing, 6-tier scoped symbol resolution.
- **IV. Change-Conditioned Retrieval & Evolution Intelligence:** Seed mapping from unified diffs, relationship-weighted PPR, logarithmic cost Dijkstra, historical Git co-change mining, tri-part hybrid score fusion.
- **V. Test Impact Analysis (TIA) & Causal Error Prediction:** Multi-tier test localization, AST signature-diff error checking.
- **VI. System Implementation & Interactive Visual Analytics:** Next.js dynamic force-directed canvas with movable physics nodes, REST API architecture.
- **VII. Experimental Evaluation:** Datasets, metrics (Recall@K, Prec@K, MRR, nDCG@K), presentation and discussion of Tables I, II, III, and IV.
- **VIII. Industrial Case Study:** Bottle PR #1541 walkthrough.
- **IX. Threats to Validity & Limitations:** Dynamic dispatch, evaluation repo sizes.
- **X. Conclusion & Future Work:** Summary and road to neural edge learning.
- **References:** Full IEEE bibliography format (citing RepoGraph ICLR 2025, SWE-bench, CodePlan, RepoCoder, Agentless).

Ensure every mathematical symbol is rigorously defined and all table numbers match the live repository benchmark data provided above.
```

