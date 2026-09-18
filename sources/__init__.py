"""
Sources package for ingesting code repositories via GitHub REST API or local filesystem.
"""
from sources.base import BaseSourceLoader
from sources.local_loader import LocalLoader
from sources.github_client import GitHubClient

__all__ = [
    "BaseSourceLoader",
    "LocalLoader",
    "GitHubClient",
]
