"""
GitHub REST API Source Loader.
Enables Zero-Clone repository analysis directly via GitHub API.
Fetches repository tree, raw file contents, and Pull Request / Commit unified diffs.
"""
import os
import logging
from typing import Dict, Optional, List
import requests

from sources.base import BaseSourceLoader
from parsers.factory import ParserFactory

logger = logging.getLogger("github_client")


class GitHubClient(BaseSourceLoader):
    def __init__(
        self,
        repo_slug: str,  # "owner/repo"
        branch: Optional[str] = None,
        pr_number: Optional[int] = None,
        commit_sha: Optional[str] = None,
        token: Optional[str] = None,
        max_files: int = 100
    ):
        parts = repo_slug.strip().replace("https://github.com/", "").strip("/").split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid GitHub repository slug: '{repo_slug}'. Expected 'owner/repo'.")
        self.owner, self.repo = parts[0], parts[1]
        self.branch = branch
        self.pr_number = pr_number
        self.commit_sha = commit_sha
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.max_files = max_files
        self.api_base = "https://api.github.com"
        self.supported_extensions = set(ParserFactory.supported_extensions())

    def _get_headers(self, accept: str = "application/vnd.github.v3+json") -> Dict[str, str]:
        headers = {"Accept": accept, "User-Agent": "Codelysis-RepoGraph"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def get_default_branch(self) -> str:
        """Fetch the repository's default branch name."""
        if self.branch:
            return self.branch
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                self.branch = resp.json().get("default_branch", "main")
                return self.branch
        except Exception as e:
            logger.warning(f"Failed to fetch default branch: {e}")
        self.branch = "main"
        return self.branch

    def load_all_files(self) -> Dict[str, str]:
        """Fetch all supported source files in repository using Git Trees API."""
        branch = self.get_default_branch()
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/git/trees/{branch}?recursive=1"
        files_dict: Dict[str, str] = {}

        logger.info(f"Fetching GitHub tree for {self.owner}/{self.repo}@{branch}...")
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code != 200:
                logger.error(f"GitHub API error ({resp.status_code}): {resp.text}")
                return files_dict

            tree = resp.json().get("tree", [])
            candidate_paths = [
                item["path"] for item in tree
                if item.get("type") == "blob" and any(item["path"].lower().endswith(ext) for ext in self.supported_extensions)
            ]

            # Prioritize first max_files files
            paths_to_fetch = candidate_paths[:self.max_files]
            logger.info(f"Fetching {len(paths_to_fetch)} source files via raw GitHub usercontent...")

            for path in paths_to_fetch:
                raw_url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{branch}/{path}"
                raw_resp = requests.get(raw_url, headers=self._get_headers(), timeout=10)
                if raw_resp.status_code == 200:
                    files_dict[path] = raw_resp.text
                else:
                    logger.debug(f"Failed to fetch file content for {path}: {raw_resp.status_code}")

        except Exception as e:
            logger.error(f"Error loading files from GitHub: {e}")

        logger.info(f"Successfully loaded {len(files_dict)} files from GitHub API")
        return files_dict

    def get_diff(self) -> Optional[str]:
        """Fetch unified diff from Pull Request, Commit, or latest commit."""
        # 1. Pull Request Diff
        if self.pr_number:
            url = f"{self.api_base}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
            logger.info(f"Fetching PR #{self.pr_number} diff from GitHub API...")
            try:
                resp = requests.get(url, headers=self._get_headers(accept="application/vnd.github.v3.diff"), timeout=15)
                if resp.status_code == 200:
                    return resp.text.strip()
            except Exception as e:
                logger.warning(f"Failed to fetch PR diff: {e}")

        # 2. Specific Commit Diff
        if self.commit_sha:
            url = f"{self.api_base}/repos/{self.owner}/{self.repo}/commits/{self.commit_sha}"
            logger.info(f"Fetching commit {self.commit_sha} diff from GitHub API...")
            try:
                resp = requests.get(url, headers=self._get_headers(accept="application/vnd.github.v3.diff"), timeout=15)
                if resp.status_code == 200:
                    return resp.text.strip()
            except Exception as e:
                logger.warning(f"Failed to fetch commit diff: {e}")

        # 3. Latest Commit Diff
        branch = self.get_default_branch()
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/commits/{branch}"
        logger.info(f"Fetching latest commit diff on branch '{branch}'...")
        try:
            resp = requests.get(url, headers=self._get_headers(accept="application/vnd.github.v3.diff"), timeout=15)
            if resp.status_code == 200:
                return resp.text.strip()
        except Exception as e:
            logger.warning(f"Failed to fetch latest commit diff: {e}")

        return None
