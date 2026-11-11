"""
Hybrid Structural, Evolutionary, and Semantic Retrieval Module.
Combines:
  1. Structural Causal Graph Traversal (RepoGraph + MultiDiGraph)
  2. Software Evolution Intelligence (Git Historical Co-Changes)
  3. Lexical / Semantic Content Relevance (Code Token Overlap)
Codelysis Extension for RepoGraph (ICLR 2025).
"""

import re
import math
import logging
from typing import Dict, List, Set, Any, Tuple, Optional, Union
from dataclasses import dataclass, field
import networkx as nx

from traversal.weighted_traversal import calculate_change_conditioned_ranking, RankedImpactNode
from sources.git_cochange import GitCoChangeMiner, CoChangeRelation

logger = logging.getLogger("hybrid_retriever")


@dataclass
class HybridRetrievalResult:
    node_id: str
    name: str
    file: str
    line: int
    category: str
    hybrid_score: float
    graph_score: float
    evolution_score: float
    semantic_score: float
    rank: int
    severity: str
    explanation: str
    evidence_path: List[Dict[str, Any]] = field(default_factory=list)
    impact_category: str = "direct_structural"  # "direct_structural", "indirect_structural", "historical_cochange", "lexical_semantic_candidate", "uncertain_relationship"
    confidence_level: str = "confirmed_high"    # "confirmed_high", "confirmed_medium", "heuristic_candidate", "low_confidence"
    evidence_sources: List[str] = field(default_factory=list)
    is_modification_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "category": self.category,
            "hybrid_score": round(self.hybrid_score, 4),
            "graph_score": round(self.graph_score, 4),
            "evolution_score": round(self.evolution_score, 4),
            "semantic_score": round(self.semantic_score, 4),
            "rank": self.rank,
            "severity": self.severity,
            "explanation": self.explanation,
            "evidence_path": self.evidence_path,
            "impact_category": self.impact_category,
            "confidence_level": self.confidence_level,
            "evidence_sources": self.evidence_sources,
            "is_modification_required": self.is_modification_required,
        }


def extract_tokens(text: str) -> Set[str]:
    """Tokenize code snippet or diff into identifiers, words, and subwords."""
    if not text:
        return set()
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    tokens = set()
    for t in raw:
        # Include full token
        tokens.add(t.lower())
        # Split by underscore (snake_case)
        for part in t.split("_"):
            if part:
                tokens.add(part.lower())
                # CamelCase split
                subwords = re.sub(r"([A-Z][a-z]+)", r" \1", part).split()
                for sw in subwords:
                    tokens.add(sw.lower())
    return {t for t in tokens if len(t) > 2}


def compute_semantic_similarity(diff_tokens: Set[str], node_data: Dict[str, Any]) -> float:
    """Compute Jaccard token overlap between diff content and target node text."""
    if not diff_tokens:
        return 0.0

    node_text = f"{node_data.get('name', '')} {node_data.get('snippet', '')} {node_data.get('docstring', '')}"
    node_tokens = extract_tokens(node_text)
    if not node_tokens:
        return 0.0

    intersection = len(diff_tokens.intersection(node_tokens))
    union = len(diff_tokens.union(node_tokens))
    return intersection / union if union > 0 else 0.0


def retrieve_hybrid_impact(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    seed_nodes: List[Dict[str, Any]],
    diff_text: str = "",
    repo_path: Optional[str] = None,
    git_miner: Optional[GitCoChangeMiner] = None,
    alpha: float = 0.65,  # Graph structural weight
    beta: float = 0.20,   # Git evolution weight
    gamma: float = 0.15,  # Semantic lexical weight
    top_k: int = 25
) -> List[HybridRetrievalResult]:
    """
    Executes hybrid retrieval combining static graph causal propagation,
    historical Git evolution mining, and semantic token relevance.
    """
    # Normalize weights so they sum to 1.0
    tot_weight = float(alpha + beta + gamma)
    if tot_weight > 0:
        norm_alpha = alpha / tot_weight
        norm_beta = beta / tot_weight
        norm_gamma = gamma / tot_weight
    else:
        norm_alpha, norm_beta, norm_gamma = 0.65, 0.20, 0.15

    # 1. Structural Causal Graph Traversal
    ranked_graph_nodes = calculate_change_conditioned_ranking(graph, seed_nodes)
    graph_node_map = {n.node_id: n for n in ranked_graph_nodes}

    # 2. Historical Git Evolution Miner
    miner = git_miner
    if miner is None and repo_path:
        miner = GitCoChangeMiner(repo_path)

    seed_files = list({node.get("file", "") for node in seed_nodes if node.get("file")})
    diff_tokens = extract_tokens(diff_text)

    # 3. Fuse scores for all candidate nodes
    hybrid_results: List[HybridRetrievalResult] = []
    seed_ids = {node["node_id"] for node in seed_nodes if "node_id" in node}

    for nid, data in graph.nodes(data=True):
        if nid in seed_ids:
            continue

        g_node = graph_node_map.get(nid)
        g_score = g_node.impact_score if g_node else 0.0

        # Evolution score
        file_path = data.get("file", "")
        e_score = miner.get_evolution_score(seed_files, file_path) if miner and file_path else 0.0

        # Semantic score
        s_score = compute_semantic_similarity(diff_tokens, data)

        # Unified Hybrid Score (linear combination with normalized heuristic weights)
        hybrid_score = (norm_alpha * g_score) + (norm_beta * e_score) + (norm_gamma * s_score)

        # Filter out completely unrelated components
        if hybrid_score < 0.05 and g_score <= 0.0:
            continue

        # Track contributing evidence sources
        evidence_sources = []
        if g_score > 0.05:
            evidence_sources.append("structural_graph")
        if e_score > 0.05:
            evidence_sources.append("git_evolution")
        if s_score > 0.10:
            evidence_sources.append("token_lexical")

        # Determine Impact Category & Confidence Classification
        cat = data.get("category", "")
        if g_node and g_node.primary_relationship == "E_invoke_candidate":
            impact_category = "uncertain_relationship"
            confidence_level = "heuristic_candidate"
        elif g_node and g_node.hop_distance == 1 and g_score >= 0.40:
            impact_category = "direct_structural"
            confidence_level = "confirmed_high"
        elif g_node and g_score >= 0.15:
            impact_category = "indirect_structural"
            confidence_level = "confirmed_medium"
        elif e_score >= 0.15:
            impact_category = "historical_cochange"
            confidence_level = "heuristic_candidate"
        elif s_score >= 0.10:
            impact_category = "lexical_semantic_candidate"
            confidence_level = "heuristic_candidate"
        else:
            impact_category = "uncertain_relationship"
            confidence_level = "low_confidence"

        # Severity classification based on fused score
        if hybrid_score >= 0.60 or (g_node and g_node.severity == "CRITICAL"):
            sev = "CRITICAL"
        elif hybrid_score >= 0.35 or (g_node and g_node.severity == "HIGH"):
            sev = "HIGH"
        elif hybrid_score >= 0.15:
            sev = "MEDIUM"
        else:
            sev = "LOW"

        # Explanation synthesizing evidence sources
        explanation_parts = []
        if g_node and g_score > 0.10:
            explanation_parts.append(g_node.causal_explanation)
        if e_score > 0.10:
            explanation_parts.append(f"Historically co-changes with modified files (evolution coupling: {round(e_score, 2)}).")
        if s_score > 0.15:
            explanation_parts.append(f"High semantic token overlap with modified diff ({round(s_score * 100, 1)}%).")

        final_explanation = " ".join(explanation_parts) if explanation_parts else (
            g_node.causal_explanation if g_node else "Structural and semantic dependency."
        )

        hybrid_results.append(
            HybridRetrievalResult(
                node_id=nid,
                name=data.get("name", ""),
                file=data.get("file", ""),
                line=data.get("line", 0),
                category=cat,
                hybrid_score=hybrid_score,
                graph_score=g_score,
                evolution_score=e_score,
                semantic_score=s_score,
                rank=0,
                severity=sev,
                explanation=final_explanation,
                evidence_path=g_node.evidence_path if g_node else [],
                impact_category=impact_category,
                confidence_level=confidence_level,
                evidence_sources=evidence_sources,
                is_modification_required=False,
            )
        )

    # Sort descending by hybrid score
    hybrid_results.sort(key=lambda r: r.hybrid_score, reverse=True)
    for idx, res in enumerate(hybrid_results, start=1):
        res.rank = idx

    return hybrid_results[:top_k]
