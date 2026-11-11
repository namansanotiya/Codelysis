"""
Weighted, Relationship-Aware Graph Traversal & Change-Conditioned Impact Ranking.
Codelysis Extension for RepoGraph (ICLR 2025).

Implements:
  1. Typed relationship edge weights:
       - E_invoke: 1.0 * confidence (highest causal dependency)
       - E_override: 0.95 (behavioral contract alteration)
       - E_inherit / E_implement: 0.85 (type hierarchy coupling)
       - E_import: 0.60 (module boundary coupling)
       - E_contain: 0.50 (lexical structural containment)
       - E_invoke_candidate: 0.25 * confidence (ambiguous candidate)
  2. Change-Conditioned Personalized PageRank / Decay Path Propagation
  3. Calibrated Impact Ranking with Explainable Severity Tiers (CRITICAL, HIGH, MEDIUM, LOW)
"""

import math
import logging
from typing import Dict, List, Set, Any, Tuple, Optional, Union
from dataclasses import dataclass, field
import networkx as nx

from core.types import EdgeType, get_edges_between

logger = logging.getLogger("weighted_traversal")

# Canonical relationship weights
RELATIONSHIP_BASE_WEIGHTS = {
    EdgeType.E_INVOKE.value: 1.00,
    EdgeType.E_OVERRIDE.value: 0.95,
    EdgeType.E_INHERIT.value: 0.85,
    EdgeType.E_IMPLEMENT.value: 0.85,
    EdgeType.E_IMPORT.value: 0.60,
    EdgeType.E_CONTAIN.value: 0.50,
    EdgeType.E_INVOKE_CANDIDATE.value: 0.25,
}


@dataclass
class RankedImpactNode:
    node_id: str
    name: str
    file: str
    line: int
    category: str
    impact_score: float
    rank: int
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    hop_distance: int
    primary_relationship: str
    causal_explanation: str
    evidence_path: List[Dict[str, Any]] = field(default_factory=list)
    impact_category: str = "direct_structural"  # "direct_structural", "indirect_structural", "historical_cochange", "lexical_semantic_candidate", "uncertain_relationship"
    evidence_source: str = "structural_ast"      # "structural_ast", "git_history", "token_similarity", "candidate_fallback"
    confidence_classification: str = "confirmed_high"  # "confirmed_high", "confirmed_medium", "heuristic_candidate", "low_confidence"
    is_modification_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "category": self.category,
            "impact_score": round(self.impact_score, 4),
            "rank": self.rank,
            "severity": self.severity,
            "hop_distance": self.hop_distance,
            "primary_relationship": self.primary_relationship,
            "causal_explanation": self.causal_explanation,
            "evidence_path": self.evidence_path,
            "impact_category": self.impact_category,
            "evidence_source": self.evidence_source,
            "confidence_classification": self.confidence_classification,
            "is_modification_required": self.is_modification_required,
        }


def _safe_cost(weight: float) -> float:
    """
    Transform positive multiplicative weight into non-negative additive Dijkstra cost:
    cost = -log(weight). Handles zero, negative, missing, or NaN weights safely.
    Higher weight/confidence gives lower cost, guaranteeing selection of the strongest path.
    """
    try:
        w = float(weight)
        if math.isnan(w) or w <= 0.0:
            return 10.0  # high penalty cost for invalid/zero weights
        w = min(1.0, max(1e-4, w))
        return -math.log(w)
    except (TypeError, ValueError):
        return 10.0


def compute_edge_weight(edge_attrs: Dict[str, Any]) -> float:
    """Compute normalized relationship weight modulated by confidence score."""
    edge_type = edge_attrs.get("edge_type", "")
    base_weight = RELATIONSHIP_BASE_WEIGHTS.get(edge_type, 0.40)
    try:
        confidence = float(edge_attrs.get("confidence", 1.0))
        if math.isnan(confidence) or confidence <= 0.0:
            confidence = 0.50
    except (TypeError, ValueError):
        confidence = 1.0
    return max(1e-4, min(1.0, base_weight * confidence))


def pure_python_ppr(
    graph: nx.DiGraph,
    seeds: List[str],
    alpha: float = 0.85,
    max_iter: int = 50,
    tol: float = 1e-5
) -> Dict[str, float]:
    """
    Pure Python implementation of Personalized PageRank / Random Walk with Restart.
    Requires no numpy or scipy, ensuring universal portability and zero runtime overhead.
    """
    nodes = list(graph.nodes())
    if not nodes or not seeds:
        return {}

    seed_set = set(seeds)
    p0 = {n: (1.0 / len(seed_set) if n in seed_set else 0.0) for n in nodes}
    p = dict(p0)

    out_weights = {}
    for n in nodes:
        total_w = sum(data.get("weight", 1.0) for _, _, data in graph.out_edges(n, data=True))
        out_weights[n] = total_w

    for _ in range(max_iter):
        p_next = {n: (1.0 - alpha) * p0[n] for n in nodes}
        for u in nodes:
            total_w = out_weights[u]
            p_u = p[u]
            if total_w > 0:
                for _, v, data in graph.out_edges(u, data=True):
                    w = data.get("weight", 1.0)
                    p_next[v] += alpha * p_u * (w / total_w)
            else:
                for v in nodes:
                    p_next[v] += alpha * p_u * p0[v]

        diff = sum(abs(p_next[n] - p[n]) for n in nodes)
        p = p_next
        if diff < tol:
            break

    return p
    """Compute normalized relationship weight modulated by confidence score."""
    edge_type = edge_attrs.get("edge_type", "")
    base_weight = RELATIONSHIP_BASE_WEIGHTS.get(edge_type, 0.40)
    confidence = float(edge_attrs.get("confidence", 1.0))
    return base_weight * confidence


def calculate_change_conditioned_ranking(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    seed_nodes: List[Dict[str, Any]],
    k_hops: int = 3,
    decay_factor: float = 0.75,
    restart_prob: float = 0.15
) -> List[RankedImpactNode]:
    """
    Computes change-conditioned impact scores for all nodes affected by seed modifications.

    Algorithm:
      1. Seeds are initialized with causal energy based on change severity.
      2. Energy propagates backward along callers (E_invoke) and forward along hierarchy/overrides.
      3. For each reachable node, computes maximum path energy and Personalized PageRank (PPR).
      4. Combines structural flow with path decay into a calibrated impact score in [0.0, 1.0].
      5. Assigns deterministic severity tiers:
           - CRITICAL : Direct caller / override with high confidence (score >= 0.70)
           - HIGH     : 1-2 hop caller or affected interface (score >= 0.45)
           - MEDIUM   : Indirect functional dependency (score >= 0.20)
           - LOW      : Distant or structural module dependency (score < 0.20)
    """
    if not seed_nodes or len(graph) == 0:
        return []

    seed_ids = {node["node_id"] for node in seed_nodes if "node_id" in node}
    
    # 1. Build an impact propagation digraph with weighted directed edges
    # Notice: If u calls v (u -> v via E_invoke), a change in v impacts u!
    # Therefore, causal impact flows from callee (seed) -> caller!
    impact_graph = nx.DiGraph()
    for n, d in graph.nodes(data=True):
        impact_graph.add_node(n, **d)

    for u, v, data in graph.edges(data=True):
        etype = data.get("edge_type", "")
        weight = compute_edge_weight(data)
        cost = _safe_cost(weight)

        # Invocation: u calls v (u -> v in graph). Impact flows from v to u (callee -> caller)
        if etype in (EdgeType.E_INVOKE.value, EdgeType.E_INVOKE_CANDIDATE.value):
            impact_graph.add_edge(v, u, weight=weight, cost=cost, edge_type=etype, confidence=data.get("confidence", 1.0))
            # Also weak forward impact (modifying caller might affect context passed)
            forward_w = weight * 0.30
            impact_graph.add_edge(u, v, weight=forward_w, cost=_safe_cost(forward_w), edge_type=etype, confidence=data.get("confidence", 1.0))

        # Overrides: sub_method overrides base_method (sub -> base). Impact flows in both directions
        elif etype == EdgeType.E_OVERRIDE.value:
            impact_graph.add_edge(v, u, weight=weight, cost=cost, edge_type=etype, confidence=1.0)
            rev_w = weight * 0.80
            impact_graph.add_edge(u, v, weight=rev_w, cost=_safe_cost(rev_w), edge_type=etype, confidence=1.0)

        # Inheritance: subclass inherits from superclass (sub -> super). Change in super impacts sub!
        elif etype in (EdgeType.E_INHERIT.value, EdgeType.E_IMPLEMENT.value):
            impact_graph.add_edge(v, u, weight=weight, cost=cost, edge_type=etype, confidence=1.0)

        # Import: importer -> importee. Change in importee impacts importer!
        elif etype == EdgeType.E_IMPORT.value:
            impact_graph.add_edge(v, u, weight=weight, cost=cost, edge_type=etype, confidence=1.0)

        # Containment: file/class contains method/call. Two-way structural propagation
        elif etype == EdgeType.E_CONTAIN.value:
            c_w = weight * 0.60
            impact_graph.add_edge(u, v, weight=c_w, cost=_safe_cost(c_w), edge_type=etype, confidence=1.0)
            impact_graph.add_edge(v, u, weight=c_w, cost=_safe_cost(c_w), edge_type=etype, confidence=1.0)

        else:
            def_w = weight * 0.50
            impact_graph.add_edge(u, v, weight=def_w, cost=_safe_cost(def_w), edge_type=etype, confidence=1.0)

    # 2. Compute Personalized PageRank with Restart from seed nodes
    valid_seeds = [s for s in seed_ids if s in impact_graph]
    if not valid_seeds:
        return []

    ppr_scores = pure_python_ppr(
        impact_graph,
        seeds=valid_seeds,
        alpha=(1.0 - restart_prob),
        max_iter=50
    )

    # Normalize PPR scores relative to maximum non-seed node
    non_seed_ppr = [score for nid, score in ppr_scores.items() if nid not in seed_ids]
    max_ppr = max(non_seed_ppr) if non_seed_ppr and max(non_seed_ppr) > 0 else 1.0

    # 3. Path-based Causal Decay & Hop Tracking using Dijkstra on -log(weight) cost
    ranked_nodes: List[RankedImpactNode] = []

    for nid, data in graph.nodes(data=True):
        if nid in seed_ids:
            continue

        best_path_score = 0.0
        best_hop = 999
        best_rel = "structural"
        best_path = []

        for seed_id in valid_seeds:
            if not nx.has_path(impact_graph, seed_id, nid):
                continue

            try:
                # Find the strongest causal path by minimizing additive cost = -log(weight)
                path = nx.shortest_path(impact_graph, source=seed_id, target=nid, weight="cost")
                hop = len(path) - 1
                if hop > k_hops:
                    continue

                # Compute multiplicative path probability with decay
                path_energy = 1.0
                path_info = []
                for i in range(len(path) - 1):
                    src, dst = path[i], path[i + 1]
                    edata = impact_graph.get_edge_data(src, dst, {})
                    w = edata.get("weight", 0.5)
                    path_energy *= (w * decay_factor)
                    path_info.append({
                        "from": src,
                        "to": dst,
                        "edge_type": edata.get("edge_type", ""),
                        "confidence": edata.get("confidence", 1.0),
                        "weight": round(w, 4)
                    })

                if path_energy > best_path_score:
                    best_path_score = path_energy
                    best_hop = hop
                    best_path = path_info
                    if path_info:
                        best_rel = path_info[-1]["edge_type"]

            except Exception:
                continue

        if best_path_score <= 0.0:
            continue

        # Composite impact score combining Normalized PPR (global flow) and Path Energy (local causal link)
        norm_ppr = ppr_scores.get(nid, 0.0) / max_ppr
        composite_score = min(1.0, 0.65 * best_path_score + 0.35 * norm_ppr)

        # Determine Severity Tier & Evidence Category
        cat = data.get("category", "")
        if best_rel == EdgeType.E_INVOKE_CANDIDATE.value:
            impact_category = "uncertain_relationship"
            confidence_classification = "heuristic_candidate"
            evidence_source = "candidate_fallback"
            severity = "MEDIUM" if composite_score >= 0.40 else "LOW"
        elif best_hop == 1 and best_rel in (EdgeType.E_INVOKE.value, EdgeType.E_OVERRIDE.value, EdgeType.E_INHERIT.value, EdgeType.E_IMPLEMENT.value):
            impact_category = "direct_structural"
            confidence_classification = "confirmed_high"
            evidence_source = "structural_ast"
            severity = "CRITICAL" if composite_score >= 0.60 else "HIGH"
        elif best_hop <= 2 and cat in ("function", "method", "class"):
            impact_category = "indirect_structural"
            confidence_classification = "confirmed_medium"
            evidence_source = "structural_ast"
            severity = "HIGH" if composite_score >= 0.40 else "MEDIUM"
        else:
            impact_category = "indirect_structural"
            confidence_classification = "confirmed_medium"
            evidence_source = "structural_ast"
            severity = "MEDIUM" if composite_score >= 0.15 else "LOW"

        # Generate human-readable causal explanation
        explanation = _generate_causal_explanation(data, best_hop, best_rel, composite_score)

        ranked_nodes.append(
            RankedImpactNode(
                node_id=nid,
                name=data.get("name", ""),
                file=data.get("file", ""),
                line=data.get("line", 0),
                category=cat,
                impact_score=composite_score,
                rank=0,  # Assigned after sorting
                severity=severity,
                hop_distance=best_hop,
                primary_relationship=best_rel,
                causal_explanation=explanation,
                evidence_path=best_path,
                impact_category=impact_category,
                evidence_source=evidence_source,
                confidence_classification=confidence_classification,
                is_modification_required=False,
            )
        )

    # Sort descending by impact score
    ranked_nodes.sort(key=lambda x: x.impact_score, reverse=True)
    for idx, node in enumerate(ranked_nodes, start=1):
        node.rank = idx

    return ranked_nodes


def _generate_causal_explanation(node_data: Dict[str, Any], hop: int, rel: str, score: float) -> str:
    """Generate concise, auditable engineering explanation for why a node was ranked."""
    name = node_data.get("name", "")
    cat = node_data.get("category", "component")
    
    if hop == 1 and rel == EdgeType.E_INVOKE.value:
        return f"Direct caller ({cat} '{name}') invokes modified symbol; signature or behavioral changes propagate immediately."
    elif hop == 1 and rel == EdgeType.E_OVERRIDE.value:
        return f"Method override '{name}' implements or modifies overridden base contract affected by seed diff."
    elif hop == 1 and rel in (EdgeType.E_INHERIT.value, EdgeType.E_IMPLEMENT.value):
        return f"Direct subclass '{name}' inherits state or interface contracts modified in seed class."
    elif hop == 2 and rel == EdgeType.E_INVOKE.value:
        return f"2-hop downstream caller '{name}' depends on upstream caller directly consuming modified logic."
    elif "test" in node_data.get("file", "").lower() or "test" in name.lower():
        return f"Verification suite '{name}' asserts behavior of downstream components in affected execution path."
    else:
        return f"Transitive dependency ({hop}-hop via {rel}) with cumulative causal impact score {round(score, 3)}."
