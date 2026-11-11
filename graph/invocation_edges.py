"""
Scoped, Signature-Aware Invocation Dependency Edges (E_invoke) Module.

Connects reference/call sites (ref) to target definition sites (def)
using the centralized SymbolIndex for proper scoped resolution.

Edge direction (RepoGraph ICLR 2025, Section 3):
    ref_site_node  -->  def_site_node
    (call site)         (callee definition)

Confidence tiers (documented rationale for each score):
  Tier 1 (1.00): Intra-class `self.method()` — only one valid definition in scope
  Tier 2 (0.95): Explicitly imported symbol — import resolved to exact module
  Tier 3 (0.90): Import with module mismatch fallback or module-attr receiver
  Tier 4 (0.95): Local definition in the same file (unambiguous local call)
  Tier 5 (0.70): Same-directory sibling module (likely but not confirmed import)
  Tier 6 (0.50): Repo-wide unique match — no other candidate with this name
  Tier 7 (0.35): Repo-wide ambiguous match — multiple candidates, lowest confidence
  UNRESOLVED: No edge created; logged at DEBUG level
"""
import os
import logging
from typing import Dict, List, Tuple, Optional, Set, Union, TYPE_CHECKING
import networkx as nx
from core.types import CodeNode, EdgeType, ImportBinding

if TYPE_CHECKING:
    from graph.symbol_index import SymbolIndex

logger = logging.getLogger("invocation_edges")


def resolve_invocation_edges(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    references: List[Tuple[str, CodeNode, Optional[str]]],
    symbol_defs: Dict[str, List[CodeNode]],
    file_imports: Optional[Dict[str, List[ImportBinding]]] = None,
    class_bases: Optional[Dict[str, List[str]]] = None,
    ignored_symbols: Optional[Set[str]] = None,
    symbol_index: Optional["SymbolIndex"] = None,
) -> int:
    """
    Resolve and wire E_invoke edges from call references to matching definitions.

    Uses SymbolIndex when available (preferred path), falls back to flat
    symbol_defs dict for backward compatibility.

    Returns the number of E_invoke edges created.
    """
    resolved_count = 0
    candidate_count = 0
    ignored = ignored_symbols or set()
    imports_map = file_imports or {}

    # Pre-build module file index for receiver resolution (backward-compat path)
    module_to_file: Dict[str, str] = {}
    for def_list in symbol_defs.values():
        for d in def_list:
            if d.file:
                clean = d.file.replace("\\", "/")
                no_ext, _ = os.path.splitext(clean)
                mod_k = no_ext.replace("/", ".").strip(".")
                module_to_file[mod_k] = d.file

    for rel_path, ref_node, enclosing_def_id in references:
        called_symbol = ref_node.name
        if called_symbol in ignored and called_symbol not in symbol_defs:
            continue

        receiver = ref_node.metadata.get("receiver")
        parent_scope = ref_node.parent_scope

        # ----------------------------------------------------------------------
        # Preferred path: use centralized SymbolIndex
        # ----------------------------------------------------------------------
        if symbol_index is not None:
            candidates = symbol_index.resolve(
                name=called_symbol,
                from_file=rel_path,
                scope=parent_scope,
                receiver=receiver,
            )
        else:
            # Backward-compat: reproduce tier logic using symbol_defs dict
            candidates = _resolve_fallback(
                called_symbol, rel_path, parent_scope, receiver,
                symbol_defs, imports_map, module_to_file, enclosing_def_id
            )

        # Wire edges for each resolved candidate
        for target_def, conf, resolution_method in candidates:
            # Note: Recursive calls (target_def.node_id == enclosing_def_id) are intentionally
            # preserved as E_invoke self-dependency edges per RepoGraph specification.
            is_recursive = (target_def.node_id == enclosing_def_id)

            if called_symbol in ignored and resolution_method in ("repo_ambiguous", "repo_unique"):
                # Skip third-party fallbacks even when found by name coincidence
                continue

            # Build evidence string for auditability
            evidence = _build_evidence(
                called_symbol, resolution_method, rel_path, target_def, receiver, is_recursive
            )

            # Distinguish confirmed E_invoke from uncertain repo_ambiguous candidates
            is_ambiguous = (resolution_method == "repo_ambiguous")
            edge_type_val = EdgeType.E_INVOKE_CANDIDATE.value if is_ambiguous else EdgeType.E_INVOKE.value

            edge_attrs = {
                "edge_type": edge_type_val,
                "confidence": conf,
                "resolution_method": resolution_method,
                "evidence": evidence,
                "symbol": called_symbol,
                "call_site_line": ref_node.line,
                "receiver": receiver or "",
                "is_recursive": is_recursive,
                "is_candidate": is_ambiguous,
            }

            if graph.is_multigraph():
                key = f"{edge_type_val}:{target_def.node_id}" if is_ambiguous else EdgeType.E_INVOKE.value
                graph.add_edge(
                    ref_node.node_id,
                    target_def.node_id,
                    key=key,
                    **edge_attrs
                )
            else:
                graph.add_edge(ref_node.node_id, target_def.node_id, **edge_attrs)

            if is_ambiguous:
                candidate_count += 1
            else:
                resolved_count += 1

    logger.info(
        f"Resolved {resolved_count} confirmed E_invoke edges "
        f"and {candidate_count} E_invoke_candidate edges with scoped confidence scoring"
    )
    return resolved_count


def _build_evidence(
    symbol: str,
    method: str,
    from_file: str,
    target: CodeNode,
    receiver: Optional[str],
    is_recursive: bool = False,
) -> str:
    """Build a human-readable evidence string for an invocation edge."""
    rec_prefix = "Recursive self-call: " if is_recursive else ""
    if method == "intra_class":
        return f"{rec_prefix}self.{symbol}() resolved within class scope in {from_file}"
    elif method == "import_exact":
        return f"{rec_prefix}'{symbol}' imported and resolved to {target.file}:{target.line}"
    elif method == "import_fallback":
        return f"{rec_prefix}'{symbol}' imported (module mismatch fallback) -> {target.file}:{target.line}"
    elif method == "module_attr":
        return f"{rec_prefix}'{receiver}.{symbol}()' module-attribute call resolved to {target.file}:{target.line}"
    elif method == "local_exact":
        return f"{rec_prefix}'{symbol}' defined locally in {from_file}:{target.line}"
    elif method == "sibling_module":
        return f"{rec_prefix}'{symbol}' found in sibling module {target.file}:{target.line}"
    elif method == "repo_unique":
        return f"{rec_prefix}'{symbol}' unique in repo -> {target.file}:{target.line}"
    elif method == "repo_ambiguous":
        return f"[Unresolved candidate] '{symbol}' ambiguous ({target.file}:{target.line} is one of multiple repo candidates)"
    return f"{rec_prefix}'{symbol}' -> {target.file}:{target.line}"


def _resolve_fallback(
    called_symbol: str,
    rel_path: str,
    parent_scope: str,
    receiver: Optional[str],
    symbol_defs: Dict[str, List[CodeNode]],
    imports_map: Dict[str, List[ImportBinding]],
    module_to_file: Dict[str, str],
    enclosing_def_id: Optional[str],
) -> List[Tuple[CodeNode, float, str]]:
    """
    Backward-compat resolution using flat symbol_defs dict.
    Mirrors SymbolIndex.resolve() tier structure without the index.
    """
    bindings = imports_map.get(rel_path, [])
    alias_lookup: Dict[str, ImportBinding] = {b.alias: b for b in bindings}
    results: List[Tuple[CodeNode, float, str]] = []

    # Tier 1: Intra-class self/cls
    if receiver in ("self", "this", "cls") and parent_scope and "." in parent_scope:
        enclosing_class = parent_scope.split(".")[0]
        qualified_method = f"{enclosing_class}.{called_symbol}"
        for d in symbol_defs.get(qualified_method, []):
            if d.file == rel_path:
                results.append((d, 1.00, "intra_class"))
        if results:
            return results

    # Tier 2: Directly imported symbol
    if called_symbol in alias_lookup:
        binding = alias_lookup[called_symbol]
        real_symbol = binding.symbol or called_symbol
        for cand in symbol_defs.get(real_symbol, []):
            cand_mod = os.path.splitext(cand.file.replace("\\", "/"))[0].replace("/", ".").strip(".")
            if binding.module and (cand_mod.endswith(binding.module) or binding.module.endswith(cand_mod)):
                results.append((cand, 0.95, "import_exact"))
        if not results:
            for cand in symbol_defs.get(real_symbol, []):
                results.append((cand, 0.90, "import_fallback"))
        if results:
            return results

    # Tier 3: Module-attribute receiver
    if receiver and receiver in alias_lookup and not results:
        binding = alias_lookup[receiver]
        target_file = module_to_file.get(binding.module)
        for cand in symbol_defs.get(called_symbol, []):
            if not target_file or cand.file == target_file:
                results.append((cand, 0.90, "module_attr"))
        if results:
            return results

    # Tier 4: Same-file local
    if not results:
        for cand in symbol_defs.get(called_symbol, []):
            if cand.file == rel_path:
                results.append((cand, 0.95, "local_exact"))
        if results:
            return results

    # Tier 5: Sibling module
    if not results:
        current_dir = os.path.dirname(rel_path.replace("\\", "/"))
        for cand in symbol_defs.get(called_symbol, []):
            if os.path.dirname(cand.file.replace("\\", "/")) == current_dir:
                results.append((cand, 0.70, "sibling_module"))
        if results:
            return results

    # Tier 6: Repo-wide fallback
    if not results:
        candidates = symbol_defs.get(called_symbol, [])
        if candidates:
            conf = 0.50 if len(candidates) == 1 else 0.35
            method = "repo_unique" if len(candidates) == 1 else "repo_ambiguous"
            for cand in candidates:
                results.append((cand, conf, method))

    return results
