"""
Seed Node Extractor.
Maps Git diff changed line numbers to corresponding RepoGraph Seed Nodes (S ⊂ V).
"""
import logging
from typing import List, Dict, Set, Any
import networkx as nx

from parsers.diff_parser import parse_unified_diff

logger = logging.getLogger("seed_extractor")


def extract_seed_nodes(graph: nx.DiGraph, diff_text: str) -> List[Dict[str, Any]]:
    """
    Identifies seed nodes S ⊂ V in RepoGraph G that correspond to lines modified in diff_text.
    """
    file_changes = parse_unified_diff(diff_text)
    if not file_changes:
        logger.warning("No modified files or lines parsed from diff text.")
        return []

    seed_nodes_set: Set[str] = set()
    seed_nodes_info: List[Dict[str, Any]] = []

    graph_files = {data.get("file") for _, data in graph.nodes(data=True) if data.get("file")}

    for diff_file_path, changed_lines in file_changes.items():
        # Match diff_file_path against graph file paths (exact or suffix)
        matched_files = [
            gf for gf in graph_files
            if gf and (gf == diff_file_path or diff_file_path.endswith(gf) or gf.endswith(diff_file_path))
        ]

        for target_file in matched_files:
            file_nodes = [
                (nid, data) for nid, data in graph.nodes(data=True)
                if data.get("file") == target_file
            ]

            matched = False
            for nid, data in file_nodes:
                line_no = data.get("line", 0)
                # Exact line match or within definition range (±2 lines)
                if line_no in changed_lines or any(abs(line_no - cl) <= 2 for cl in changed_lines):
                    if nid not in seed_nodes_set:
                        seed_nodes_set.add(nid)
                        seed_nodes_info.append(data)
                        matched = True

            # Fallback to top-level file/function node if lines weren't matched exactly
            if not matched:
                for nid, data in file_nodes:
                    if data.get("category") in ("file", "function", "class"):
                        if nid not in seed_nodes_set:
                            seed_nodes_set.add(nid)
                            seed_nodes_info.append(data)

    logger.info(f"Identified {len(seed_nodes_info)} Seed Nodes from Git diff")
    return seed_nodes_info
