"""
Local Filesystem Source Loader.
Scans local directories for supported code files and captures git diffs.
"""
import os
import subprocess
import logging
from typing import Dict, Optional, List

from sources.base import BaseSourceLoader
from parsers.factory import ParserFactory

logger = logging.getLogger("local_loader")


class LocalLoader(BaseSourceLoader):
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.supported_extensions = set(ParserFactory.supported_extensions())

    def load_all_files(self) -> Dict[str, str]:
        files_dict: Dict[str, str] = {}
        if not os.path.exists(self.repo_path):
            logger.error(f"Local repo path does not exist: {self.repo_path}")
            return files_dict

        for root, _, filenames in os.walk(self.repo_path):
            # Skip hidden and cache folders
            if any(part.startswith(".") or part in ("__pycache__", "node_modules", "target", "vendor") for part in root.split(os.sep)):
                continue

            for fname in filenames:
                _, ext = os.path.splitext(fname.lower())
                if ext in self.supported_extensions:
                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, self.repo_path).replace("\\", "/")
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            files_dict[rel_path] = f.read()
                    except Exception as e:
                        logger.warning(f"Could not read {rel_path}: {e}")

        logger.info(f"Loaded {len(files_dict)} source files from {self.repo_path}")
        return files_dict

    def get_diff(self, revision: str = "HEAD") -> Optional[str]:
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            return None

        try:
            res = subprocess.run(
                ["git", "diff", revision],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            diff_text = res.stdout.strip()
            if not diff_text:
                res_prev = subprocess.run(
                    ["git", "diff", "HEAD~1", "HEAD"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True
                )
                diff_text = res_prev.stdout.strip()
            return diff_text if diff_text else None
        except Exception as e:
            logger.debug(f"Could not fetch git diff from local repo: {e}")
            return None
