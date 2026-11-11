"""
Causal Evidence Path Tracer & Error Prediction Module.
Traces propagation paths from seed modifications to downstream callers,
and analyzes signature diffs to predict exact runtime/compile-time errors.
Codelysis Extension for RepoGraph (ICLR 2025).
"""
import re
import math
import logging
from typing import List, Dict, Set, Any, Tuple, Optional, Union
import networkx as nx

from core.types import EdgeType, has_edge_type, get_edges_between
from traversal.weighted_traversal import RELATIONSHIP_BASE_WEIGHTS, compute_edge_weight, _safe_cost

logger = logging.getLogger("path_tracer")


def compute_path_evidence_strength(formatted_path: List[Dict[str, Any]]) -> float:
    """Computes multiplicative evidence strength of a path in (0, 1]."""
    strength = 1.0
    for step in formatted_path[1:]:
        conf = float(step.get("confidence", 1.0))
        etype = step.get("edge_type", "")
        base_w = RELATIONSHIP_BASE_WEIGHTS.get(etype, 0.50)
        strength *= max(1e-4, base_w * conf)
    return strength


def trace_evidence_paths(
    ego_graph: Union[nx.DiGraph, nx.MultiDiGraph],
    seed_nodes: List[Dict[str, Any]],
    max_path_length: int = 5
) -> Dict[str, List[List[Dict[str, Any]]]]:
    """
    Find causal propagation paths from any seed node to each affected node in the ego subgraph.
    Ranks paths by multiplicative relationship evidence strength (strongest evidence path first).
    Returns: Dict[target_node_id, List of paths] where each path is a list of node dicts with edge info.
    """
    seed_ids = {node["node_id"] for node in seed_nodes if "node_id" in node}
    evidence_paths: Dict[str, List[List[Dict[str, Any]]]] = {}

    # Build weighted graph for Dijkstra shortest-cost path finding
    cost_graph = nx.DiGraph()
    for n, d in ego_graph.nodes(data=True):
        cost_graph.add_node(n, **d)

    for u, v, d in ego_graph.edges(data=True):
        w = compute_edge_weight(d)
        c = _safe_cost(w)
        etype = d.get("edge_type", "")
        conf = d.get("confidence", 1.0)
        cost_graph.add_edge(u, v, weight=w, cost=c, edge_type=etype, confidence=conf)

    # For each target node in ego_graph
    for target_nid, target_data in ego_graph.nodes(data=True):
        if target_nid in seed_ids:
            continue

        target_paths = []
        for seed_id in seed_ids:
            if seed_id not in ego_graph:
                continue

            try:
                # 1. Forward path from seed to target (weighted Dijkstra via cost)
                if nx.has_path(cost_graph, seed_id, target_nid):
                    best_forward = nx.shortest_path(cost_graph, source=seed_id, target=target_nid, weight="cost")
                    if len(best_forward) - 1 <= max_path_length:
                        fpath = []
                        for i, nid in enumerate(best_forward):
                            ndata = dict(ego_graph.nodes[nid])
                            step_info = {
                                "node_id": nid,
                                "name": ndata.get("name", ""),
                                "file": ndata.get("file", ""),
                                "line": ndata.get("line", 0),
                                "category": ndata.get("category", "")
                            }
                            if i > 0:
                                prev_nid = best_forward[i - 1]
                                edges = get_edges_between(ego_graph, prev_nid, nid)
                                step_info["edge_type"] = edges[0].get("edge_type", "") if edges else ""
                                step_info["confidence"] = edges[0].get("confidence", 1.0) if edges else 1.0
                            fpath.append(step_info)
                        target_paths.append(fpath)

                # 2. Reverse path from target (caller) to seed via E_invoke
                if nx.has_path(cost_graph, target_nid, seed_id):
                    best_rev = nx.shortest_path(cost_graph, source=target_nid, target=seed_id, weight="cost")
                    if len(best_rev) - 1 <= max_path_length:
                        rev_rp = list(reversed(best_rev))
                        rpath = []
                        for i, nid in enumerate(rev_rp):
                            ndata = dict(ego_graph.nodes[nid])
                            step_info = {
                                "node_id": nid,
                                "name": ndata.get("name", ""),
                                "file": ndata.get("file", ""),
                                "line": ndata.get("line", 0),
                                "category": ndata.get("category", "")
                            }
                            if i > 0:
                                next_nid = rev_rp[i - 1]
                                edges = get_edges_between(ego_graph, nid, next_nid)
                                step_info["edge_type"] = edges[0].get("edge_type", "") if edges else ""
                                step_info["confidence"] = edges[0].get("confidence", 1.0) if edges else 1.0
                            rpath.append(step_info)
                        target_paths.append(rpath)

            except Exception as e:
                logger.debug(f"Path tracing error: {e}")

        if target_paths:
            # Sort paths by multiplicative evidence strength (descending: strongest first)
            target_paths.sort(key=compute_path_evidence_strength, reverse=True)
            # Deduplicate by node sequence
            unique_paths = []
            seen_seqs = set()
            for p in target_paths:
                seq = tuple(step["node_id"] for step in p)
                if seq not in seen_seqs:
                    seen_seqs.add(seq)
                    unique_paths.append(p)
            evidence_paths[target_nid] = unique_paths[:2]
            # Sort paths by length (shortest first) and deduplicate
            target_paths.sort(key=len)
            evidence_paths[target_nid] = target_paths[:2]

    return evidence_paths


def predict_potential_errors(
    ego_graph: Union[nx.DiGraph, nx.MultiDiGraph],
    seed_nodes: List[Dict[str, Any]],
    diff_text: str = ""
) -> List[Dict[str, Any]]:
    """
    Analyzes seed modifications and downstream call references to predict specific runtime/compile errors:
    1. Signature Mismatch (added parameters without default values)
    2. Missing Argument Errors at Call Sites
    3. Overridden Method Signature Incompatibility
    4. Broken Unit Test Assertions
    """
    predicted_errors: List[Dict[str, Any]] = []
    seed_ids = {node["node_id"] for node in seed_nodes if "node_id" in node}

    # Inspect diff for parameter additions
    added_params = set()
    removed_params = set()
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            matches = re.findall(r"([A-Za-z0-9_]+)\s*:\s*[A-Za-z0-9_\[\],\s]+(?:=\s*[^,)]+)?", line)
            for m in matches:
                if "=" not in line[line.find(m):]:
                    added_params.add(m)
        elif line.startswith("-") and not line.startswith("---"):
            matches = re.findall(r"([A-Za-z0-9_]+)\s*:\s*[A-Za-z0-9_\[\],\s]+", line)
            for m in matches:
                removed_params.add(m)

    for seed in seed_nodes:
        seed_id = seed.get("node_id", "")
        seed_name = seed.get("name", "")
        seed_file = seed.get("file", "")
        seed_sig = seed.get("signature", "")

        # Find all callers pointing to this seed via E_invoke
        callers = []
        for pred in ego_graph.predecessors(seed_id):
            if has_edge_type(ego_graph, pred, seed_id, EdgeType.E_INVOKE.value):
                callers.append((pred, ego_graph.nodes[pred]))

        for caller_id, cdata in callers:
            cfile = cdata.get("file", "")
            cline = cdata.get("line", 0)
            cname = cdata.get("name", "")
            csnippet = cdata.get("snippet", "")
            arg_count = cdata.get("metadata", {}).get("arg_count", 0)

            # Check if this call is in a test file
            is_test = "test" in cfile.lower()

            if is_test:
                predicted_errors.append({
                    "severity": "HIGH",
                    "error_type": "AssertionError / TestFailure",
                    "file": cfile,
                    "line": cline,
                    "symbol": cname,
                    "snippet": csnippet,
                    "cause": f"Unit test directly exercises modified symbol '{seed_name}'.",
                    "recommended_fix": f"Update test assertions and mock payloads in {cfile}:{cline} to reflect changed behavior."
                })
            else:
                predicted_errors.append({
                    "severity": "CRITICAL" if added_params else "HIGH",
                    "error_type": "TypeError: CallSignatureMismatch" if added_params else "DownstreamRegressionRisk",
                    "file": cfile,
                    "line": cline,
                    "symbol": cname,
                    "snippet": csnippet,
                    "cause": f"Call site '{cname}' in {cfile} invokes '{seed_name}' whose definition/signature was modified in {seed_file}.",
                    "recommended_fix": f"Update call arguments at {cfile}:L{cline} to match the new signature of '{seed_name}'."
                })

        # Check overriding methods
        for pred in ego_graph.predecessors(seed_id):
            if has_edge_type(ego_graph, pred, seed_id, EdgeType.E_OVERRIDE.value):
                odata = ego_graph.nodes[pred]
                predicted_errors.append({
                    "severity": "HIGH",
                    "error_type": "LiskovSubstitutionViolation / SignatureMismatch",
                    "file": odata.get("file", ""),
                    "line": odata.get("line", 0),
                    "symbol": odata.get("name", ""),
                    "snippet": odata.get("snippet", ""),
                    "cause": f"Subclass method '{odata.get('name')}' overrides modified base method '{seed_name}'.",
                    "recommended_fix": f"Synchronize parameter types and return annotations in {odata.get('file')}:L{odata.get('line')}."
                })

    return predicted_errors

