"""
Abstract Base Parser interface for RepoGraph code line & symbol extraction.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
from core.types import CodeNode, ImportBinding


class BaseParser(ABC):
    """
    Base parser interface.
    Each language parser transforms source code into:
    1. definitions: List[CodeNode]
    2. references: List[Tuple[CodeNode, Optional[str]]] (ref_node, enclosing_def_node_id)
    """

    @abstractmethod
    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        """
        Parse source code content and extract line-level definitions and call references.
        """
        pass

    def get_imports(self) -> List[ImportBinding]:
        """Return list of imported modules and symbol bindings from last parse."""
        return []

    def get_class_bases(self) -> Dict[str, List[str]]:
        """Return mapping of class_name -> list of superclass names from last parse."""
        return {}

    @staticmethod
    def get_snippet(lines: List[str], line_no: int) -> str:
        """Helper to get stripped line content (1-indexed)."""
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1].strip()
        return ""
