"""
Historical Co-Change Intelligence & Evolution Mining Module.
Extracts historical co-change patterns from Git commit history
to augment static code graph retrieval with software evolution intelligence.
Codelysis Extension for RepoGraph (ICLR 2025).
"""

import os
import subprocess
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger("git_cochange")


@dataclass
class CoChangeRelation:
    source_file: str
    target_file: str
    co_change_count: int
    jaccard_score: float
    confidence: float
    support: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "target_file": self.target_file,
            "co_change_count": self.co_change_count,
            "jaccard_score": round(self.jaccard_score, 4),
            "confidence": round(self.confidence, 4),
            "support": self.support,
        }


class GitCoChangeMiner:
    """
    Mines Git version control history to extract file-level co-change couplings.
    Enforces temporal integrity: supports `before_commit` and `before_date` boundaries
    and commit exclusions to strictly prevent future data leakage.
    """

    def __init__(
        self,
        repo_path: str,
        max_commits: int = 500,
        before_commit: Optional[str] = None,
        before_date: Optional[str] = None,
        exclude_commits: Optional[Set[str]] = None,
    ):
        self.repo_path = repo_path
        self.max_commits = max_commits
        self.before_commit = before_commit
        self.before_date = before_date
        self.exclude_commits = set(exclude_commits) if exclude_commits else set()
        self.file_commit_counts: Dict[str, int] = {}
        self.pair_co_change_counts: Dict[Tuple[str, str], int] = {}
        self.total_analyzed_commits: int = 0
        self.is_git_available: bool = False

        self._mine_history()

    def _mine_history(self) -> None:
        """Parse git log with temporal boundaries to build co-change frequency tables."""
        git_dir = os.path.join(self.repo_path, ".git")
        if not os.path.exists(git_dir):
            # Check if repo_path is inside a git repo
            try:
                check = subprocess.run(
                    ["git", "rev-parse", "--is-inside-work-tree"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if check.returncode != 0:
                    logger.debug(f"Path '{self.repo_path}' is not a Git repository.")
                    return
            except Exception:
                return

        try:
            cmd = [
                "git", "log",
                f"-n{self.max_commits}",
                "--name-only",
                '--format=format:COMMIT_HASH:%H'
            ]
            if self.before_date:
                cmd.append(f"--before={self.before_date}")
            if self.before_commit:
                # Exclude evaluated commit and future commits by starting from its parent
                cmd.append(f"{self.before_commit}~1")

            res = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                # Fallback: if before_commit~1 failed (e.g. root commit), try with exclude_commits
                if self.before_commit:
                    cmd_fallback = [
                        "git", "log",
                        f"-n{self.max_commits}",
                        "--name-only",
                        '--format=format:COMMIT_HASH:%H'
                    ]
                    if self.before_date:
                        cmd_fallback.append(f"--before={self.before_date}")
                    res = subprocess.run(cmd_fallback, cwd=self.repo_path, capture_output=True, text=True, timeout=15)
                    self.exclude_commits.add(self.before_commit)
                    if res.returncode != 0:
                        logger.warning(f"Git log execution failed: {res.stderr}")
                        return
                else:
                    logger.warning(f"Git log execution failed: {res.stderr}")
                    return

            self.is_git_available = True
            lines = res.stdout.splitlines()
            current_commit_hash = ""
            current_commit_files: Set[str] = set()

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("COMMIT_HASH:"):
                    if current_commit_hash and current_commit_hash not in self.exclude_commits:
                        self._process_commit(current_commit_files)
                        self.total_analyzed_commits += 1
                    current_commit_hash = line.replace("COMMIT_HASH:", "").strip()
                    current_commit_files = set()
                else:
                    # Normalized relative file path
                    clean_path = line.replace("\\", "/").strip()
                    if clean_path:
                        current_commit_files.add(clean_path)

            # Process final commit
            if current_commit_hash and current_commit_hash not in self.exclude_commits:
                self._process_commit(current_commit_files)
                self.total_analyzed_commits += 1

            logger.info(
                f"Mined Git co-change history: {self.total_analyzed_commits} commits, "
                f"{len(self.file_commit_counts)} files, {len(self.pair_co_change_counts)} pairwise relations."
            )

        except Exception as e:
            logger.warning(f"Error while mining git log: {e}")

    def load_in_memory_commits(self, commits: List[Tuple[str, List[str]]]) -> None:
        """Directly load commit history records for deterministic evaluation."""
        self.file_commit_counts.clear()
        self.pair_co_change_counts.clear()
        self.total_analyzed_commits = 0
        for chash, files in commits:
            if chash in self.exclude_commits:
                continue
            self._process_commit(set(files))
            self.total_analyzed_commits += 1
        self.is_git_available = True

    def _process_commit(self, files: Set[str]) -> None:
        """Record file changes and pairwise co-changes in one commit."""
        # Exclude giant merge/vendor commits (> 40 files) to avoid noise
        if not files or len(files) > 40:
            return

        file_list = sorted(list(files))
        for f in file_list:
            self.file_commit_counts[f] = self.file_commit_counts.get(f, 0) + 1

        for i in range(len(file_list)):
            for j in range(i + 1, len(file_list)):
                pair = (file_list[i], file_list[j])
                self.pair_co_change_counts[pair] = self.pair_co_change_counts.get(pair, 0) + 1

    def get_co_changed_files(
        self,
        seed_files: List[str],
        min_support: int = 1,
        min_jaccard: float = 0.05
    ) -> List[CoChangeRelation]:
        """
        Returns ranked list of files historically co-changed with the given seed files.
        """
        results: List[CoChangeRelation] = []
        normalized_seeds = {f.replace("\\", "/").strip() for f in seed_files}

        for (f1, f2), count in self.pair_co_change_counts.items():
            if count < min_support:
                continue

            target = None
            source = None
            if f1 in normalized_seeds and f2 not in normalized_seeds:
                source, target = f1, f2
            elif f2 in normalized_seeds and f1 not in normalized_seeds:
                source, target = f2, f1

            if target and source:
                c1 = self.file_commit_counts.get(source, 1)
                c2 = self.file_commit_counts.get(target, 1)
                union = c1 + c2 - count
                jaccard = count / union if union > 0 else 0.0
                confidence = count / c1 if c1 > 0 else 0.0

                if jaccard >= min_jaccard:
                    results.append(
                        CoChangeRelation(
                            source_file=source,
                            target_file=target,
                            co_change_count=count,
                            jaccard_score=jaccard,
                            confidence=confidence,
                            support=count
                        )
                    )

        # Sort descending by Jaccard score then confidence
        results.sort(key=lambda r: (r.jaccard_score, r.confidence), reverse=True)
        return results

    def get_evolution_score(self, seed_files: List[str], target_file: str) -> float:
        """
        Calculates evolutionary coupling score between seed files and target file in [0.0, 1.0].
        """
        clean_target = target_file.replace("\\", "/").strip()
        best_score = 0.0

        for sf in seed_files:
            clean_seed = sf.replace("\\", "/").strip()
            if clean_seed == clean_target:
                continue

            pair = tuple(sorted([clean_seed, clean_target]))
            count = self.pair_co_change_counts.get(pair, 0)
            if count > 0:
                c1 = self.file_commit_counts.get(clean_seed, 1)
                c2 = self.file_commit_counts.get(clean_target, 1)
                union = c1 + c2 - count
                jaccard = count / union if union > 0 else 0.0
                best_score = max(best_score, jaccard)

        return min(1.0, best_score)

