"""
Graph-RAG Engine module.
Serializes k-hop Ego Subgraph into clean, structured prompt context for LLM reasoning.
"""
import logging
from typing import List, Dict, Any, Set
import networkx as nx

from code_impact_graph_rag.config import MAX_CONTEXT_SIZE

logger = logging.getLogger("graph_rag_engine")


def serialize_ego_graph(ego_graph: nx.DiGraph, seed_nodes: List[Dict[str, Any]], diff_text: str = "") -> str:
    """
    Serialize Ego Subgraph G_ego and Git Diff into structured textual context for LLM input.
    Organizes nodes by File -> Symbols -> Code Snippets -> Execution & Invocation Relationships.
    """
    if ego_graph.number_of_nodes() == 0:
        return "No subgraph nodes identified for analysis."

    lines: List[str] = []
    lines.append("=== GRAPH-RAG REPOSITORY SUBGRAPH CONTEXT ===")
    lines.append("")

    # 1. Diff Section
    lines.append("--- GIT DIFF / CHANGED CODE ---")
    if diff_text:
        lines.append(diff_text.strip())
    else:
        lines.append("(No diff text provided)")
    lines.append("")

    # 2. Seed Nodes Section
    lines.append("--- MODIFIED SEED SYMBOLS ---")
    seed_ids = {node["node_id"] for node in seed_nodes if "node_id" in node}
    for snode in seed_nodes:
        file_path = snode.get("file", "unknown")
        line = snode.get("line", 0)
        name = snode.get("name", "unknown")
        cat = snode.get("category", "symbol")
        snippet = snode.get("snippet", "")
        lines.append(f"- SEED: [{cat.upper()}] {name} (File: {file_path}, Line: {line})")
        if snippet:
            lines.append(f"  Code: `{snippet}`")
    lines.append("")

    # 3. Group Ego Graph Nodes by File
    files_map: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for nid, data in ego_graph.nodes(data=True):
        file_path = data.get("file", "unknown")
        files_map.setdefault(file_path, []).append((nid, data))

    lines.append("--- REPOSITORY DEPENDENCY SUBGRAPH ---")

    for file_path in sorted(files_map.keys()):
        node_entries = files_map[file_path]
        lines.append(f"FILE: {file_path}")

        # Separate defs and refs
        defs = [(nid, d) for nid, d in node_entries if d.get("type") == "def"]
        defs.sort(key=lambda x: x[1].get("line", 0))

        for nid, d in defs:
            category = d.get("category", "symbol").upper()
            name = d.get("name", "unknown")
            line = d.get("line", 0)
            snippet = d.get("snippet", "")
            is_seed = nid in seed_ids

            seed_tag = " [MODIFIED SEED]" if is_seed else ""
            lines.append(f"  {category}: {name}{seed_tag} (Line {line})")
            if snippet:
                lines.append(f"    Code: {snippet}")

            # Relationships for this definition node
            # Called by (Inbound E_invoke to call refs contained inside other defs)
            incoming_calls: List[str] = []
            for pred in ego_graph.predecessors(nid):
                edge_data = ego_graph.get_edge_data(pred, nid, {})
                if edge_data.get("edge_type") == "E_invoke":
                    # Find container of pred
                    pred_data = ego_graph.nodes[pred]
                    caller_file = pred_data.get("file", "")
                    caller_line = pred_data.get("line", 0)
                    caller_name = pred_data.get("name", "")
                    
                    # Look up enclosing container if available
                    enclosing_containers = [
                        ego_graph.nodes[p].get("name", "")
                        for p in ego_graph.predecessors(pred)
                        if ego_graph.get_edge_data(p, pred, {}).get("edge_type") == "E_contain"
                    ]
                    container_str = f" in {enclosing_containers[0]}" if enclosing_containers else ""
                    incoming_calls.append(f"{caller_name} ({caller_file}:{caller_line}{container_str})")

            if incoming_calls:
                lines.append("    Called by:")
                for caller in incoming_calls:
                    lines.append(f"      - {caller}")

            # Calls (Outbound E_contain -> ref -> E_invoke -> target def)
            outgoing_calls: List[str] = []
            for succ in ego_graph.successors(nid):
                edge_data = ego_graph.get_edge_data(nid, succ, {})
                if edge_data.get("edge_type") == "E_contain" and ego_graph.nodes[succ].get("type") == "ref":
                    ref_data = ego_graph.nodes[succ]
                    # Follow E_invoke to target def
                    for target in ego_graph.successors(succ):
                        if ego_graph.get_edge_data(succ, target, {}).get("edge_type") == "E_invoke":
                            target_data = ego_graph.nodes[target]
                            t_name = target_data.get("name", "")
                            t_file = target_data.get("file", "")
                            t_line = target_data.get("line", 0)
                            outgoing_calls.append(f"{t_name} ({t_file}:{t_line})")

            if outgoing_calls:
                lines.append("    Calls:")
                for callee in outgoing_calls:
                    lines.append(f"      - {callee}")

        lines.append("")

    serialized = "\n".join(lines)

    # Truncate if exceeds MAX_CONTEXT_SIZE
    if len(serialized) > MAX_CONTEXT_SIZE:
        logger.warning(f"Context size ({len(serialized)} chars) exceeds limit ({MAX_CONTEXT_SIZE}). Truncating...")
        serialized = serialized[:MAX_CONTEXT_SIZE] + "\n... [CONTEXT TRUNCATED DUE TO SIZE LIMIT]"

    return serialized


def build_llm_prompts(graph_context: str, diff_text: str) -> Dict[str, str]:
    """
    Construct System and User Prompts for LLM Code Change Impact Analysis.
    """
    system_prompt = (
        "You are an expert Software Architect and Code Change Impact Analyzer.\n"
        "Your task is to analyze a code modification (Git diff) alongside its extracted repository dependency graph (Graph-RAG context).\n"
        "Identify all downstream files, symbols, function callers, class implementations, and test cases affected by the change.\n"
        "Provide structured recommendations detailing affected files, line numbers, reason for impact, required changes, and confidence score."
    )

    user_prompt = f"""
Analyze the following Git diff and repository dependency graph context to determine all affected code components.

{graph_context}

Provide a structured Markdown report answering:
1. **Summary of Change**: What functions/methods/signatures/logic were changed?
2. **Affected Files & Line Numbers**: Which files and specific lines are impacted?
3. **Impact Rationale**: Why is each file impacted (e.g. direct caller, indirect caller, changed signature, test case)?
4. **Recommended Co-Changes**: What specific updates/refactors are needed in each affected file?
5. **Testing Requirements**: Which test files need updating or new test cases added?

Format the output clearly in GitHub-flavored Markdown.
"""
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt
    }
