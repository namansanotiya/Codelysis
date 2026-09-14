"""
Git Diff Parser & Seed Node Identifier module.
Parses Git diffs, extracts modified line numbers per file, and maps them to graph Seed Nodes (S ⊂ V).
"""
import re
import os
import subprocess
import logging
from typing import List, Dict, Set, Optional, Any
import networkx as nx

logger = logging.getLogger("diff_parser")


def parse_unified_diff(diff_text: str) -> Dict[str, Set[int]]:
    """
    Parse unified git diff text and return a dictionary mapping:
    file_relative_path -> set of changed line numbers (in the new file version).
    """
    file_changes: Dict[str, Set[int]] = {}
    current_file: Optional[str] = None
    current_line: int = 0

    # Pattern for hunk headers: @@ -old_start,old_count +new_start,new_count @@
    hunk_header_re = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@")

    for line in diff_text.splitlines():
        # Check target file header
        if line.startswith("+++ b/"):
            raw_path = line[6:].strip()
            current_file = raw_path.replace("\\", "/")
            if current_file not in file_changes:
                file_changes[current_file] = set()
            continue
        elif line.startswith("--- "):
            continue

        # Check hunk header
        match = hunk_header_re.match(line)
        if match:
            current_line = int(match.group(1))
            continue

        if current_file is None or current_line == 0:
            continue

        # Process diff body lines
        if line.startswith("+"):
            file_changes[current_file].add(current_line)
            current_line += 1
        elif line.startswith("-"):
            # Line removed; record closest line in new file
            file_changes[current_file].add(current_line)
        elif line.startswith(" "):
            # Unchanged context line
            current_line += 1

    return file_changes


def get_git_diff(repo_path: str, revision: str = "HEAD") -> str:
    """Run `git diff` command in repository directory to obtain unified diff text."""
    try:
        res = subprocess.run(
            ["git", "diff", revision],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        diff_text = res.stdout.strip()
        if not diff_text:
            res_commit = subprocess.run(
                ["git", "diff", "HEAD~1", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            diff_text = res_commit.stdout.strip()
        return diff_text
    except Exception as e:
        logger.warning(f"Failed to fetch git diff automatically: {e}")
        return ""


def extract_seed_nodes(graph: nx.DiGraph, diff_text: str) -> List[Dict[str, Any]]:
    """
    Given repository graph G and unified diff text, identify seed nodes S ⊂ V
    corresponding to modified lines and symbols.
    """
    file_changes = parse_unified_diff(diff_text)
    if not file_changes:
        logger.warning("No modified files or lines parsed from diff text.")
        return []

    seed_nodes_set: Set[str] = set()
    seed_nodes_info: List[Dict[str, Any]] = []

    # Get all file paths present in graph
    graph_files = {data.get("file") for _, data in graph.nodes(data=True) if data.get("file")}

    # Map file changes to graph nodes
    for diff_file_path, changed_lines in file_changes.items():
        # Match diff_file_path against graph_files (exact or suffix match)
        matched_graph_files = [
            gf for gf in graph_files
            if gf and (gf == diff_file_path or diff_file_path.endswith(gf) or gf.endswith(diff_file_path))
        ]

        for target_file in matched_graph_files:
            matching_nodes = [
                (nid, data) for nid, data in graph.nodes(data=True)
                if data.get("file") == target_file
            ]

            matched_for_file = False
            for nid, data in matching_nodes:
                node_line = data.get("line", 0)
                # Check exact match or line within function/definition snippet scope
                if node_line in changed_lines or any(abs(node_line - cl) <= 2 for cl in changed_lines):
                    if nid not in seed_nodes_set:
                        seed_nodes_set.add(nid)
                        seed_nodes_info.append(data)
                        matched_for_file = True

            # Fallback: if no specific symbol line matched but file exists in graph, add file node
            if not matched_for_file:
                for nid, data in matching_nodes:
                    if data.get("category") in ("file", "function", "class"):
                        if nid not in seed_nodes_set:
                            seed_nodes_set.add(nid)
                            seed_nodes_info.append(data)

    logger.info(f"Identified {len(seed_nodes_info)} Seed Nodes from Git diff")
    return seed_nodes_info
