"""
Data models for Diff parsing, Impact Analysis, and Recommendations.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set, Any
from core.types import CodeNode


@dataclass
class DiffChange:
    """Represents changed lines in a modified file."""
    file_path: str
    changed_lines: Set[int] = field(default_factory=set)


@dataclass
class ImpactSummary:
    """Summary of k-hop ego subgraph analysis."""
    seed_nodes: List[Dict[str, Any]] = field(default_factory=list)
    direct_callers: List[Dict[str, Any]] = field(default_factory=list)
    indirect_callers: List[Dict[str, Any]] = field(default_factory=list)
    callees: List[Dict[str, Any]] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    total_ego_nodes: int = 0
    total_ego_edges: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed_nodes": self.seed_nodes,
            "direct_callers": self.direct_callers,
            "indirect_callers": self.indirect_callers,
            "callees": self.callees,
            "affected_files": self.affected_files,
            "total_ego_nodes": self.total_ego_nodes,
            "total_ego_edges": self.total_ego_edges
        }


@dataclass
class CoChangeReport:
    """Generated markdown report and metadata."""
    markdown_content: str
    affected_files: List[str] = field(default_factory=list)
    confidence: str = "high"
