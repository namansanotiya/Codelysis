"""
Graph Schema definitions for RepoGraph (ICLR 2025) and Codelysis Extensions.
Defines Nodes (V) and Edges (E) types, attributes, and graph helpers.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Set, Optional, Union
import networkx as nx


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
    IMPORT = "import"
    VARIABLE = "variable"
    FIELD = "field"


class EdgeType(str, Enum):
    E_CONTAIN = "E_contain"    # Structural containment: container -> internal component
    E_INVOKE = "E_invoke"      # Invocation dependency: reference site -> target definition
    E_INVOKE_CANDIDATE = "E_invoke_candidate"  # Unresolved or ambiguous candidate invocation
    E_IMPORT = "E_import"      # Import relationship: importing file/scope -> imported target
    E_INHERIT = "E_inherit"    # Class inheritance: subclass -> superclass
    E_OVERRIDE = "E_override"  # Method override: overriding method -> overridden base method
    E_IMPLEMENT = "E_implement"# Interface realization: class -> interface


@dataclass
class ImportBinding:
    """Represents an imported symbol and its local alias binding."""
    module: str
    symbol: str               # Exported symbol name or '*' or empty
    alias: str                # Name bound in local scope
    is_from_import: bool = True
    line: int = 0


@dataclass
class CodeNode:
    """
    Represents a code line or entity node in RepoGraph G = (V, E)
    with enriched source-location spans and semantic coordinates.
    """
    node_id: str
    file: str
    line: int
    name: str
    type: str        # 'def' or 'ref'
    category: str    # 'file', 'class', 'struct', 'function', 'method', 'call', etc.
    end_line: int = 0
    start_col: int = 0
    end_col: int = 0
    qualified_name: str = ""
    signature: str = ""
    docstring: str = ""
    parent_scope: str = ""
    snippet: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EdgeData:
    """Metadata payload attached to a graph edge."""
    edge_type: str
    confidence: float = 1.0
    symbol: str = ""
    alias: str = ""
    call_site_line: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Multi-Graph & Graph Helper Functions (Transparent DiGraph & MultiDiGraph support)
# ==============================================================================

def get_edges_between(graph: Union[nx.DiGraph, nx.MultiDiGraph], u: str, v: str) -> List[Dict[str, Any]]:
    """Return list of edge attribute dictionaries between node u and v."""
    if not graph.has_edge(u, v):
        return []
    edge_data = graph.get_edge_data(u, v)
    if graph.is_multigraph():
        # returns {key0: attr0, key1: attr1, ...}
        return list(edge_data.values())
    # returns attr dict
    return [edge_data]


def get_edge_types(graph: Union[nx.DiGraph, nx.MultiDiGraph], u: str, v: str) -> Set[str]:
    """Return set of edge_type strings present between node u and v."""
    types = set()
    for d in get_edges_between(graph, u, v):
        et = d.get("edge_type")
        if et:
            types.add(et)
    return types


def has_edge_type(graph: Union[nx.DiGraph, nx.MultiDiGraph], u: str, v: str, edge_type: str) -> bool:
    """Check if an edge with specific edge_type exists between u and v."""
    return edge_type in get_edge_types(graph, u, v)
