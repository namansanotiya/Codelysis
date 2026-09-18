"""
Diff parser compatibility wrapper.
"""
from parsers.diff_parser import parse_unified_diff
from traversal.seed_extractor import extract_seed_nodes
from sources.local_loader import LocalLoader


def get_git_diff(repo_path: str, revision: str = "HEAD") -> str:
    loader = LocalLoader(repo_path)
    return loader.get_diff(revision) or ""


__all__ = ["parse_unified_diff", "extract_seed_nodes", "get_git_diff"]
