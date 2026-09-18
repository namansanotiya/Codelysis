"""
Base Source Loader Interface.
Defines methods to load repository source files and diffs.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseSourceLoader(ABC):
    """Abstract interface for repository source ingestion."""

    @abstractmethod
    def load_all_files(self) -> Dict[str, str]:
        """
        Load supported source files from repository into a dictionary of:
        {relative_file_path: file_content_str}
        """
        pass

    @abstractmethod
    def get_diff(self) -> Optional[str]:
        """
        Fetch the unified git diff representing the changes to analyze.
        """
        pass
