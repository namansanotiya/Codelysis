"""
Graph-RAG Subgraph Serializer (RepoGraph ICLR 2025, Section 3.2 & Figure 9).
Serializes k-hop Ego Subgraphs into structured hierarchical text
with support for MultiDiGraph edges, confidence annotations, imports, and inheritance.
"""
import logging
from typing import List, Dict, Any, Tuple, Union, Optional
import networkx as nx
from core.types import EdgeType, has_edge_type, get_edges_between

logger = logging.getLogger("rag_serializer")


def serialize_ego_graph(
    ego_graph: Union[nx.DiGraph, nx.MultiDiGraph],
    seed_nodes: List[Dict[str, Any]],
    diff_text: str = "",
    test_recommendations: Optional[List[Dict[str, Any]]] = None,
    max_context_size: int = 8000
) -> str:
    """
    Serialize Ego Subgraph G_ego, Git Diff, and Relevant Tests into structured textual context for LLM reasoning.
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
        end_line = snode.get("end_line", 0)
        line_span = f"L{line}-L{end_line}" if end_line and end_line != line else f"Line: {line}"
        name = snode.get("name", "unknown")
        cat = snode.get("category", "symbol")
        sig = snode.get("signature", "")
        snippet = snode.get("snippet", "")
        sig_str = f" `{sig}`" if sig else ""
        lines.append(f"- SEED: [{cat.upper()}] {name}{sig_str} (File: {file_path}, {line_span})")
        if snippet:
            lines.append(f"  Code: `{snippet}`")
    lines.append("")

    # 2b. Test Impact Analysis Section
    if test_recommendations:
        lines.append("--- SUGGESTED RELEVANT TESTS (TEST IMPACT ANALYSIS) ---")
        for tr in test_recommendations:
            tfile = tr.get("test_file", "")
            tname = tr.get("test_name", "")
            cls = tr.get("classification", "")
            score = tr.get("impact_score", 0.0)
            reason = tr.get("reason", "")
            lines.append(f"- [{cls.upper()}] {tname} ({tfile}) - Impact Score: {score:.2f}")
            lines.append(f"  Reason: {reason}")
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
            sig = d.get("signature", "")
            snippet = d.get("snippet", "")
            is_seed = nid in seed_ids

            seed_tag = " [MODIFIED SEED]" if is_seed else ""
            sig_str = f" {sig}" if sig else ""
            lines.append(f"  {category}: {name}{sig_str}{seed_tag} (Line {line})")
            if snippet:
                lines.append(f"    Code: {snippet}")

            # Inbound calls (Called by:)
            incoming_calls: List[str] = []
            for pred in ego_graph.predecessors(nid):
                if has_edge_type(ego_graph, pred, nid, EdgeType.E_INVOKE.value):
                    pred_data = ego_graph.nodes[pred]
                    caller_file = pred_data.get("file", "")
                    caller_line = pred_data.get("line", 0)
                    caller_name = pred_data.get("name", "")

                    containers = [
                        ego_graph.nodes[p].get("name", "")
                        for p in ego_graph.predecessors(pred)
                        if has_edge_type(ego_graph, p, pred, EdgeType.E_CONTAIN.value)
                    ]
                    container_str = f" in {containers[0]}" if containers else ""
                    
                    # Extract confidence score if available
                    edge_list = get_edges_between(ego_graph, pred, nid)
                    conf_str = ""
                    for ed in edge_list:
                        if ed.get("edge_type") == EdgeType.E_INVOKE.value and "confidence" in ed:
                            conf_str = f" [conf: {ed['confidence']:.2f}]"
                            break

                    incoming_calls.append(f"{caller_name} ({caller_file}:{caller_line}{container_str}){conf_str}")

                elif has_edge_type(ego_graph, pred, nid, EdgeType.E_OVERRIDE.value):
                    pred_data = ego_graph.nodes[pred]
                    incoming_calls.append(f"[OVERRIDDEN BY] {pred_data.get('name', '')} ({pred_data.get('file', '')}:{pred_data.get('line', 0)})")

            if incoming_calls:
                lines.append("    Called by / Overridden by:")
                for caller in incoming_calls:
                    lines.append(f"      - {caller}")

            # Outbound calls (Calls:)
            outgoing_calls: List[str] = []
            for succ in ego_graph.successors(nid):
                if has_edge_type(ego_graph, nid, succ, EdgeType.E_CONTAIN.value) and ego_graph.nodes[succ].get("type") == "ref":
                    for target in ego_graph.successors(succ):
                        if has_edge_type(ego_graph, succ, target, EdgeType.E_INVOKE.value):
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
