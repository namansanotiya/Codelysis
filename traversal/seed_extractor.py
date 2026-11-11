"""
Seed Node Extractor.
Maps Git diff changed line numbers to corresponding RepoGraph Seed Nodes (S ⊂ V)
using precise AST line spans [start_line, end_line] and lexical enclosure.
"""
import logging
from typing import List, Dict, Set, Any, Union
import networkx as nx

from parsers.diff_parser import parse_unified_diff

logger = logging.getLogger("seed_extractor")


def extract_seed_nodes(graph: Union[nx.DiGraph, nx.MultiDiGraph], diff_text: str) -> List[Dict[str, Any]]:
    """
    Identifies seed nodes S ⊂ V in RepoGraph G that correspond to lines modified in diff_text.
    Leverages AST start_line and end_line bounds for exact enclosure matching.
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
                end_line = data.get("end_line", 0) or line_no

                # 1. Check exact enclosure within AST node span [line_no, end_line]
                in_span = any(line_no <= cl <= end_line for cl in changed_lines)
                # 2. Check boundary tolerance (within ±2 lines of start/end)
                near_boundary = any(abs(line_no - cl) <= 2 or abs(end_line - cl) <= 2 for cl in changed_lines)

                if in_span or near_boundary:
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
