# PROMPT FOR CHATGPT: Generate Video Recording Script, Flowcharts & Slide Deck

> **Instructions for User**: Copy everything below this line and paste it directly into ChatGPT (GPT-4o or Claude 3.5 Sonnet) to generate your complete **Video Presentation Recording Script**, **Mermaid Flowcharts/Visualizers**, and **Slide Deck**.

---

### 🤖 COPY & PASTE THE PROMPT BELOW INTO CHATGPT 🤖

```text
Act as a Senior Principal Software Architect, Video Production Director, and Technical Presentation Expert. 

I am recording a VIDEO PRESENTATION (Voiceover + Screencast/Slides) for my End-Term Project (ETP) titled:
"Graph-RAG Code Change Impact Analysis & Co-Change Recommender" (based on RepoGraph framework, ICLR 2025).

Below is the complete technical architecture, data flow, code schema, and traversal trace of my project. Read and analyze it thoroughly, then create a complete VIDEO RECORDING SCRIPT with word-for-word voiceover narration, visual cues/screen transitions, ASCII/Mermaid flowcharts for every slide, and a python-pptx slide generation script.

================================================================================
                               PROJECT BLUEPRINT & DATA FLOW
================================================================================

1. INGESTION PHASE:
   - File Ingestion (`graph_builder.py: scan_repo_files`): Recursively scans project directories using `os.walk()`. Filters out vendor/build directories (`node_modules`, `venv`, `dist`, `build`, `.git`) and ingests multi-language source files (`.py`, `.js`, `.jsx`, `.ts`, `.tsx`, `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.go`).
   - Git Diff Ingestion (`diff_parser.py: get_git_diff & parse_unified_diff`): Retrieves unified Git diff (`git diff HEAD`). Parses hunk headers (`@@ -old,count +new,count @@`) using regex `^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@` to isolate modified files and exact changed line numbers in the new file version.

2. PARSING & AST ANALYSIS PHASE:
   - Python AST Visitor (`PythonASTVisitor`): Uses native Python `ast` module to traverse Abstract Syntax Trees (`visit_ClassDef`, `visit_FunctionDef`, `visit_AsyncFunctionDef`, `visit_Call`). Tracks nested lexical scope to distinguish functions from class methods.
   - Multi-Language Pattern Parser (`parse_generic_source`): Uses regular expressions for JS/TS, Java, C/C++, and Go to detect classes, structs, interfaces, functions, methods, and call sites (`\b([A-Za-z0-9_]+)\s*\(`).

3. RELATION FILTERING PHASE:
   - Standard Library & Keyword Exclusion (`config.py: STDLIB_MODULES & BUILTIN_KEYWORDS`): Excludes language keywords (`if`, `else`, `while`, `for`, `switch`, `return`, `import`) and built-in standard library calls (`print`, `len`, `console.log`, `System.out.println`, `fmt.Println`, `os`, `sys`, `json`).
   - Noise Reduction: Strips out external dependencies so the dependency graph isolates purely internal repository components.

4. GRAPH CONSTRUCTION PHASE:
   - Directed Graph Schema G = (V, E) built with NetworkX (`nx.DiGraph`).
   - Nodes (V): Represented as `CodeNode` with schema `file:L<line>:<type>:<name>`. Types: `def` (definition site) vs `ref` (reference call site). Categories: `file`, `class`, `function`, `method`, `call`.
   - Edges (E):
     a. `E_contain` (Structural Edge): Parent Container -> Inner definition / call site (File -> Function, Class -> Method).
     b. `E_invoke` (Invocation Edge): Call Reference Node (`ref`) -> Target Definition Node (`def`).
   - Assembly Algorithm: 
     - Pass 1: Scan source files -> register File & Definition nodes -> store definitions in symbol lookup map.
     - Pass 2: Scan reference calls -> link enclosing containers -> resolve target symbol in lookup map -> add `E_invoke` edges.

5. EGO-GRAPH & k-HOP TRAVERSAL PHASE:
   - Seed Node Identification (`extract_seed_nodes`): Maps changed line numbers from Git diff to matching graph nodes S ⊆ V.
   - Bidirectional BFS Traversal (`impact_analyzer.py: extract_ego_graph`): Performs Breadth-First Search up to k=2 hops starting from Seed Nodes S:
     - Forward Traversal (Successors): Traces outgoing edges to discover callees and internal sub-functions.
     - Backward Traversal (Predecessors): Traces incoming edges to discover direct callers, indirect callers, parent classes, and test suites.
   - Example Traversal Trace (Refactoring `validate_token` in `auth/service.py`):
     - Seed Node: `auth/service.py:L3:def:validate_token`
     - Hop 1 Backward: Direct call sites `core/service.py:L6:ref:validate_token` and `tests/test_auth.py:L5:ref:validate_token`.
     - Hop 2 Backward: Parent definitions `CoreProcessor.process_request` and `test_validate_token_success`.
     - Hop 1 Forward: Callee `auth/token.py:L1:def:decode_token`.
     - Resulting Ego Subgraph G_ego: 11 nodes, 11 edges spanning 4 affected files.

6. RAG SERIALIZATION PHASE (`graph_rag_engine.py: serialize_ego_graph`):
   - Flattens G_ego into structured Markdown prompt context:
     - Section 1: Git Diff header.
     - Section 2: Modified Seed Symbols & code snippets.
     - Section 3: Subgraph hierarchy grouped by FILE -> Definitions -> Code Snippets -> Inbound Callers -> Outbound Calls.
   - Context Window Capping (`MAX_CONTEXT_SIZE = 8000` chars): Truncates context to protect LLM context windows.

7. LLM REASONING & FALLBACK PHASE (`recommender.py`):
   - Queries Google Gemini API (`gemini-2.5-flash`) or OpenAI API (`gpt-4o`).
   - Rule-Based Fallback Engine (`generate_compact_recommendation_report`): If no API key is provided, deterministically generates a file-grouped Markdown impact report detailing:
     - High Impact (Direct Invocations): Required argument updates.
     - Test Suite Impact: Required assertion updates.
     - Medium Impact (2-hop Dependencies): Required workflow verification.

8. LIVE WATCH MODE (`demo.py: watch_repository`):
   - Real-time IDE integration polling `os.path.getmtime`. Re-analyzes graph impact instantly upon file save.

================================================================================
                       WHAT YOU NEED TO GENERATE FOR VIDEO RECORDING
================================================================================

Please generate a comprehensive 10 to 12-Slide Video Presentation Package. For EVERY slide / video segment, provide:

1. 🎬 **Slide Title & Video Timestamp Target** (e.g. `[00:00 - 00:45] Slide 1: Introduction & Problem Statement`).
2. 📊 **Visualizer / Flowchart (Mandatory Mermaid Code Block)**: Provide explicit, copy-pasteable `mermaid` flowchart/diagram code for each slide to visualize that specific phase (e.g., Ingestion flowchart, AST parsing tree, Graph schema diagram, 2-hop BFS traversal flowchart, RAG serialization context flow).
3. 🎥 **On-Screen Action / Screen Sharing Directions**: Specify what to show on screen (e.g., `[SHOW ON SCREEN: Slide Diagram]`, `[SCREENSHARE SWITCH: Terminal running demo.py --watch]`, `[HIGHLIGHT: Red box around seed node]`).
4. 🎙️ **Word-for-Word Voiceover Video Script**: Write a natural, clear, highly engaging word-for-word spoken script that I will read out loud while recording the video. Include narration cues like `[Pause]`, `[Emphasize]`, `[Point to diagram]`.
5. ❓ **Anticipated Jury/Evaluator Question & Defense Answer**: 1 tricky technical question a reviewer might ask after watching this section, with the exact defense answer.

Finally, include a complete Python script using `python-pptx` to generate the presentation slides automatically with placeholder sections for the Mermaid visualizers.
```
