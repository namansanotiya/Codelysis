"""
Graph Schema definitions for RepoGraph (ICLR 2025).
Defines Nodes (V) and Edges (E) types and attributes.
"""
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any


class NodeType(str, Enum):
    DEF = "def"  # Definition site
    REF = "ref"  # Reference / invocation site


class Category(str, Enum):
    FILE = "file"
    CLASS = "class"
    STRUCT = "struct"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    CALL = "call"


class EdgeType(str, Enum):
    E_CONTAIN = "E_contain"  # Structural containment: container -> internal component
    E_INVOKE = "E_invoke"    # Invocation dependency: reference site -> target definition


@dataclass
class CodeNode:
    """
    Represents a code line or entity node in RepoGraph G = (V, E).
    """
    node_id: str
    file: str
    line: int
    name: str
    type: str        # 'def' or 'ref'
    category: str    # 'file', 'class', 'struct', 'function', 'method', 'call'
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
