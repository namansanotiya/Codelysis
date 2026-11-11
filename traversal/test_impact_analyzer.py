"""
Test Impact Analysis (TIA) Module.
Identifies and classifies potentially relevant test files and test functions
affected by a code modification, using code-to-test invocations, import dependencies,
transitive call paths, and historical Git co-change intelligence.
Codelysis Extension for RepoGraph (ICLR 2025).
"""
import re
import os
import logging
from typing import List, Dict, Set, Any, Optional, Union
from dataclasses import dataclass, field
import networkx as nx

from core.types import EdgeType, has_edge_type, get_edges_between
from traversal.weighted_traversal import RankedImpactNode

logger = logging.getLogger("test_impact_analyzer")


def is_test_entity(file_path: str, entity_name: str = "") -> bool:
    """Determine whether a file or function corresponds to a test component."""
    norm_file = file_path.replace("\\", "/").lower()
    norm_name = entity_name.lower()
    
    file_match = (
        norm_file.startswith("test")
        or "/test" in norm_file
        or "test_" in norm_file
        or "_test." in norm_file
        or ".spec." in norm_file
        or ".test." in norm_file
    )
    name_match = norm_name.startswith("test") or norm_name.endswith("test")
    return file_match or name_match


@dataclass
class TestImpactRecommendation:
    test_file: str
    test_name: str
    test_node_id: str
    classification: str  # "directly_related", "indirectly_related", "historically_associated", "candidate_review"
    impact_score: float
    relationship_type: str
    evidence_path: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    requires_execution: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_file": self.test_file,
            "test_name": self.test_name,
            "test_node_id": self.test_node_id,
            "classification": self.classification,
            "impact_score": round(self.impact_score, 4),
            "relationship_type": self.relationship_type,
            "evidence_path": self.evidence_path,
            "reason": self.reason,
            "requires_execution": self.requires_execution,
        }


def identify_relevant_tests(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    ego_graph: Union[nx.DiGraph, nx.MultiDiGraph],
    seed_nodes: List[Dict[str, Any]],
    ranked_nodes: Optional[List[RankedImpactNode]] = None,
    co_changes: Optional[List[Dict[str, Any]]] = None,
    evidence_paths: Optional[Dict[str, List[List[Dict[str, Any]]]]] = None
) -> List[TestImpactRecommendation]:
    """
    Identifies and categorizes tests relevant to a code change.
    
    Classifications:
      1. directly_related: Test directly calls or exercises modified seed definition.
      2. indirectly_related: Test exercises a downstream component that depends on seed.
      3. historically_associated: Test file historically co-changes with modified files.
      4. candidate_review: Test imports modified module or has candidate invocation.
    """
    recommendations: List[TestImpactRecommendation] = []
    seen_test_nodes: Set[str] = set()

    seed_ids = {s.get("node_id") for s in seed_nodes if "node_id" in s}
    seed_files = {s.get("file", "") for s in seed_nodes if s.get("file")}
    ranked_node_map = {n.node_id: n for n in ranked_nodes} if ranked_nodes else {}
    path_map = evidence_paths or {}

    # ------------------------------------------------------------------
    # Category 1 & 2: Structural Call-Graph Dependencies (Direct & Indirect)
    # ------------------------------------------------------------------
    # Scan all definition nodes in the ego_graph and graph for test entities
    for nid, data in graph.nodes(data=True):
        fpath = data.get("file", "")
        name = data.get("name", "")
        ntype = data.get("type", "")
        cat = data.get("category", "")

        # Only evaluate function/method definitions in test files
        if ntype != "def" or cat not in ("function", "method"):
            continue
        if not is_test_entity(fpath, name):
            continue

        # Check if this test node or its contained call sites call a seed node
        # A test function node contains ref nodes via E_contain:
        # test_func -E_contain-> ref_site -E_invoke-> seed_def
        direct_to_seed = False
        target_seed_name = ""
        invoking_ref = None

        # Check direct calls from within this test function
        for succ in graph.successors(nid):
            if has_edge_type(graph, nid, succ, EdgeType.E_CONTAIN.value):
                # succ is a ref node inside this test function
                for target in graph.successors(succ):
                    if target in seed_ids:
                        if has_edge_type(graph, succ, target, EdgeType.E_INVOKE.value):
                            direct_to_seed = True
                            target_seed_name = graph.nodes[target].get("name", "")
                            invoking_ref = succ
                            break
            # Also check if test function itself was wired directly to seed
            if succ in seed_ids and has_edge_type(graph, nid, succ, EdgeType.E_INVOKE.value):
                direct_to_seed = True
                target_seed_name = graph.nodes[succ].get("name", "")
                break

        # Also check if seed is called directly by nid in ego_graph
        if nid in ego_graph:
            for s in seed_ids:
                if s in ego_graph and has_edge_type(ego_graph, nid, s, EdgeType.E_INVOKE.value):
                    direct_to_seed = True
                    target_seed_name = ego_graph.nodes[s].get("name", "")

        if direct_to_seed:
            seen_test_nodes.add(nid)
            ev_path = path_map.get(nid, [[]])[0] if nid in path_map else []
            rnode = ranked_node_map.get(nid)
            score = rnode.impact_score if rnode else 0.95

            recommendations.append(
                TestImpactRecommendation(
                    test_file=fpath,
                    test_name=name,
                    test_node_id=nid,
                    classification="directly_related",
                    impact_score=max(0.85, score),
                    relationship_type=EdgeType.E_INVOKE.value,
                    evidence_path=ev_path,
                    reason=f"Test function directly calls modified definition '{target_seed_name}'. Highly recommended to run.",
                    requires_execution=True
                )
            )
            continue

        # Check for Indirect (2-hop or 3-hop) test relationship
        rnode = ranked_node_map.get(nid)
        if rnode and rnode.hop_distance <= 3 and rnode.impact_score >= 0.20:
            seen_test_nodes.add(nid)
            recommendations.append(
                TestImpactRecommendation(
                    test_file=fpath,
                    test_name=name,
                    test_node_id=nid,
                    classification="indirectly_related",
                    impact_score=rnode.impact_score,
                    relationship_type=rnode.primary_relationship,
                    evidence_path=rnode.evidence_path,
                    reason=f"Test exercises downstream dependency '{rnode.name}' affected by seed change ({rnode.hop_distance} hops).",
                    requires_execution=True
                )
            )
            continue

    # ------------------------------------------------------------------
    # Category 3: Historical Co-Change Associated Tests
    # ------------------------------------------------------------------
    if co_changes:
        for cc in co_changes:
            tgt_file = cc.get("target_file", "")
            jaccard = float(cc.get("jaccard_score", 0.0))
            support = int(cc.get("support", 0))

            if is_test_entity(tgt_file) and jaccard >= 0.10:
                # Find test definitions in this file
                test_defs_in_file = [
                    (n, d) for n, d in graph.nodes(data=True)
                    if d.get("file") == tgt_file and d.get("type") == "def" and d.get("category") in ("function", "method")
                ]

                if test_defs_in_file:
                    for tn, td in test_defs_in_file:
                        if tn not in seen_test_nodes:
                            seen_test_nodes.add(tn)
                            recommendations.append(
                                TestImpactRecommendation(
                                    test_file=tgt_file,
                                    test_name=td.get("name", ""),
                                    test_node_id=tn,
                                    classification="historically_associated",
                                    impact_score=min(0.80, jaccard * 0.90),
                                    relationship_type="git_co_change",
                                    evidence_path=[{"file": tgt_file, "jaccard": jaccard, "support": support}],
                                    reason=f"Test file historically co-changes with modified files (Jaccard: {round(jaccard, 2)}, {support} shared commits).",
                                    requires_execution=True
                                )
                            )
                else:
                    # File-level test entry
                    file_nid = f"file:{tgt_file}"
                    if file_nid not in seen_test_nodes:
                        seen_test_nodes.add(file_nid)
                        recommendations.append(
                            TestImpactRecommendation(
                                test_file=tgt_file,
                                test_name=os.path.basename(tgt_file),
                                test_node_id=file_nid,
                                classification="historically_associated",
                                impact_score=min(0.80, jaccard * 0.90),
                                relationship_type="git_co_change",
                                evidence_path=[{"file": tgt_file, "jaccard": jaccard, "support": support}],
                                reason=f"Test suite historically co-changes with modified files (Jaccard: {round(jaccard, 2)}).",
                                requires_execution=True
                            )
                        )

    # ------------------------------------------------------------------
    # Category 4: Candidate Tests Requiring Manual Review
    # ------------------------------------------------------------------
    for nid, data in graph.nodes(data=True):
        if nid in seen_test_nodes:
            continue
        fpath = data.get("file", "")
        name = data.get("name", "")
        if not is_test_entity(fpath, name) or data.get("type") != "def":
            continue

        # Check if test file imports any seed file
        test_file_node = next((d for n, d in graph.nodes(data=True) if d.get("file") == fpath and d.get("category") == "file"), None)
        if test_file_node:
            for succ in graph.successors(test_file_node["node_id"]):
                succ_file = graph.nodes[succ].get("file", "")
                if succ_file in seed_files and has_edge_type(graph, test_file_node["node_id"], succ, EdgeType.E_IMPORT.value):
                    seen_test_nodes.add(nid)
                    recommendations.append(
                        TestImpactRecommendation(
                            test_file=fpath,
                            test_name=name,
                            test_node_id=nid,
                            classification="candidate_review",
                            impact_score=0.45,
                            relationship_type=EdgeType.E_IMPORT.value,
                            evidence_path=[{"file": fpath, "imported": succ_file}],
                            reason=f"Test module imports modified file '{succ_file}'. Worth manual verification.",
                            requires_execution=False
                        )
                    )
                    break

    # Sort descending by impact score
    recommendations.sort(key=lambda r: r.impact_score, reverse=True)
    return recommendations

