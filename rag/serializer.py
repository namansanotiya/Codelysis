"""
Graph-RAG Subgraph Serializer (RepoGraph ICLR 2025, Section 3.2 & Figure 9).
Serializes k-hop Ego Subgraphs into structured hierarchical text.
"""
import logging
from typing import List, Dict, Any, Tuple
import networkx as nx

logger = logging.getLogger("rag_serializer")


def serialize_ego_graph(
    ego_graph: nx.DiGraph,
    seed_nodes: List[Dict[str, Any]],
    diff_text: str = "",
    max_context_size: int = 8000
) -> str:
    """
    Serialize Ego Subgraph G_ego and Git Diff into structured textual context for LLM reasoning.
    """
    if ego_graph.number_of_nodes() == 0:
        return "No subgraph nodes identified for analysis."

    lines: List[str] = []
    lines.append("=== GRAPH-RAG REPOSITORY SUBGRAPH CONTEXT ===")
    lines.append("")

    # 1. Git Diff Section
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

            # Inbound calls (Called by:)
            incoming_calls: List[str] = []
            for pred in ego_graph.predecessors(nid):
                edge_data = ego_graph.get_edge_data(pred, nid, {})
                if edge_data.get("edge_type") == "E_invoke":
                    pred_data = ego_graph.nodes[pred]
                    caller_file = pred_data.get("file", "")
                    caller_line = pred_data.get("line", 0)
                    caller_name = pred_data.get("name", "")

                    containers = [
                        ego_graph.nodes[p].get("name", "")
                        for p in ego_graph.predecessors(pred)
                        if ego_graph.get_edge_data(p, pred, {}).get("edge_type") == "E_contain"
                    ]
                    container_str = f" in {containers[0]}" if containers else ""
                    incoming_calls.append(f"{caller_name} ({caller_file}:{caller_line}{container_str})")

            if incoming_calls:
                lines.append("    Called by:")
                for caller in incoming_calls:
                    lines.append(f"      - {caller}")

            # Outbound calls (Calls:)
            outgoing_calls: List[str] = []
            for succ in ego_graph.successors(nid):
                edge_data = ego_graph.get_edge_data(nid, succ, {})
                if edge_data.get("edge_type") == "E_contain" and ego_graph.nodes[succ].get("type") == "ref":
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
    if len(serialized) > max_context_size:
        logger.warning(f"Context exceeds {max_context_size} chars. Truncating...")
        serialized = serialized[:max_context_size] + "\n... [CONTEXT TRUNCATED DUE TO SIZE LIMIT]"

    return serialized
