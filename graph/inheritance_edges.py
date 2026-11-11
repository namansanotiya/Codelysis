"""
Inheritance, Override, and Implementation Relationship Edges Module.
Connects subclasses to superclasses (E_inherit), overriding methods to base methods (E_override),
and concrete classes to interfaces (E_implement).

RepoGraph Extension:
  (V_subclass, E_inherit, V_superclass)
  (V_subclass, E_implement, V_interface)
  (V_override_method, E_override, V_base_method)

Fixes & Hardening:
  - Uses unique class identities (node_id) to prevent duplicate class names across files overwriting each other
  - Resolves base classes through explicit module imports & file context
  - Uses qualified class ancestry to resolve overrides across inheritance chains
  - Verifies method signature compatibility (leaf name and parameter compatibility)
  - Eliminates false cross-class overrides for unrelated classes with identical method names
  - Handles multiple inheritance (multiple E_inherit edges)
  - Distinguishes E_implement (interfaces) from E_inherit (classes)
  - MultiDiGraph keying and deterministic confidence
"""
import os
import re
import logging
from typing import Dict, List, Optional, Union, Set, Tuple, TYPE_CHECKING
import networkx as nx
from core.types import CodeNode, EdgeType, Category, ImportBinding

if TYPE_CHECKING:
    from graph.symbol_index import SymbolIndex

logger = logging.getLogger("inheritance_edges")


def check_signature_compatibility(sub_sig: str, base_sig: str) -> bool:
    """
    Check if two method signatures are structurally compatible for overriding.
    Returns True if compatible or if signature info is absent/unparsed.
    """
    if not sub_sig or not base_sig or sub_sig == "()" or base_sig == "()":
        return True
    
    # Extract parameter list inside outer parentheses
    sub_match = re.search(r"\((.*)\)", sub_sig)
    base_match = re.search(r"\((.*)\)", base_sig)
    if not sub_match or not base_match:
        return True

    sub_params = [p.strip() for p in sub_match.group(1).split(",") if p.strip()]
    base_params = [p.strip() for p in base_match.group(1).split(",") if p.strip()]

    # Filter out 'self' / 'cls' / 'this'
    sub_args = [p for p in sub_params if not p.startswith(("self", "cls", "this"))]
    base_args = [p for p in base_params if not p.startswith(("self", "cls", "this"))]

    # If base method requires parameters without defaults, sub method should accept them
    base_required = [p for p in base_args if "=" not in p and not p.startswith(("*", "**"))]
    sub_required = [p for p in sub_args if "=" not in p and not p.startswith(("*", "**"))]

    # If subclass has more required parameters than base, it breaks substitution
    if len(sub_required) > len(base_required):
        # Unless subclass uses *args / **kwargs
        has_varargs = any(p.startswith(("*", "**")) for p in sub_args)
        if not has_varargs:
            return False

    return True


def resolve_inheritance_edges(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    class_bases: Dict[str, List[str]],
    symbol_defs: Dict[str, List[CodeNode]],
    file_imports: Optional[Dict[str, List[ImportBinding]]] = None,
    symbol_index: Optional["SymbolIndex"] = None
) -> int:
    """
    Resolve and wire E_inherit, E_override, and E_implement edges.
    Keyed by unique class identity (node_id or f'{file}:{name}').
    Returns total count of wired edges.
    """
    resolved_count = 0
    imports_map = file_imports or {}

    # Map class node_id -> CodeNode for instant exact lookup
    class_node_map: Dict[str, CodeNode] = {}
    for def_list in symbol_defs.values():
        for d in def_list:
            if d.category in (Category.CLASS.value, Category.STRUCT.value, Category.INTERFACE.value):
                class_node_map[d.node_id] = d

    # Pre-build ancestry graph to track class hierarchies
    ancestry_graph = nx.DiGraph()

    # Pass 1: Resolve base classes and wire E_inherit / E_implement
    for subclass_identifier, base_names in class_bases.items():
        # Step A: Identify the subclass CodeNode
        sub_candidates: List[CodeNode] = []
        if subclass_identifier in class_node_map:
            sub_candidates = [class_node_map[subclass_identifier]]
        elif subclass_identifier in symbol_defs:
            sub_candidates = [
                d for d in symbol_defs[subclass_identifier]
                if d.category in (Category.CLASS.value, Category.STRUCT.value)
            ]
        else:
            short_name = subclass_identifier.split(".")[-1].split(":")[-1]
            sub_candidates = [
                d for d in symbol_defs.get(short_name, [])
                if d.category in (Category.CLASS.value, Category.STRUCT.value)
            ]

        if not sub_candidates:
            continue

        for sub_node in sub_candidates:
            sub_file = sub_node.file
            file_bindings = imports_map.get(sub_file, [])
            alias_to_binding = {b.alias: b for b in file_bindings}

            for base_expr in base_names:
                clean_base = base_expr.split(".")[-1].strip()
                
                # Check all definitions matching this base name
                all_base_cands = [
                    d for d in symbol_defs.get(clean_base, [])
                    if d.category in (Category.CLASS.value, Category.STRUCT.value, Category.INTERFACE.value)
                    and d.node_id != sub_node.node_id
                ]

                if not all_base_cands:
                    continue

                matched_super_nodes: List[CodeNode] = []

                # Strategy 1: Check if base class was imported in this file
                if clean_base in alias_to_binding or base_expr in alias_to_binding:
                    binding = alias_to_binding.get(clean_base) or alias_to_binding.get(base_expr)
                    if binding and binding.module:
                        for cand in all_base_cands:
                            cand_mod = os.path.splitext(cand.file.replace("\\", "/"))[0].replace("/", ".").strip(".")
                            if cand_mod.endswith(binding.module) or binding.module.endswith(cand_mod) or cand.file.endswith(binding.module):
                                matched_super_nodes.append(cand)

                # Strategy 2: Check if base class is defined in the same file
                if not matched_super_nodes:
                    same_file = [d for d in all_base_cands if d.file == sub_file]
                    if same_file:
                        matched_super_nodes.extend(same_file)

                # Strategy 3: Check same directory / package
                if not matched_super_nodes:
                    sub_dir = os.path.dirname(sub_file.replace("\\", "/"))
                    same_dir = [d for d in all_base_cands if os.path.dirname(d.file.replace("\\", "/")) == sub_dir]
                    if same_dir:
                        matched_super_nodes.extend(same_dir)

                # Strategy 4: If unique in repository, safely use it
                if not matched_super_nodes and len(all_base_cands) == 1:
                    matched_super_nodes.append(all_base_cands[0])

                # Connect verified superclasses
                for super_node in matched_super_nodes:
                    is_interface = super_node.category == Category.INTERFACE.value
                    rel_edge_type = EdgeType.E_IMPLEMENT.value if is_interface else EdgeType.E_INHERIT.value
                    edge_attrs = {
                        "edge_type": rel_edge_type,
                        "confidence": 1.0,
                        "subclass": sub_node.name,
                        "superclass": super_node.name,
                        "qualified_subclass": sub_node.qualified_name or sub_node.name,
                        "qualified_superclass": super_node.qualified_name or super_node.name,
                    }
                    if graph.is_multigraph():
                        key = f"{rel_edge_type}:{super_node.node_id}"
                        graph.add_edge(sub_node.node_id, super_node.node_id, key=key, **edge_attrs)
                    else:
                        graph.add_edge(sub_node.node_id, super_node.node_id, **edge_attrs)
                    resolved_count += 1

                    # Register in ancestry graph (subclass -> superclass)
                    ancestry_graph.add_edge(sub_node.node_id, super_node.node_id)

    # Pass 2: Resolve method overrides using qualified class ancestry and signature compatibility
    all_methods = [
        d for def_list in symbol_defs.values() for d in def_list
        if d.category == Category.METHOD.value
    ]
    # Group methods by class node_id or enclosing class name
    class_methods_map: Dict[str, List[CodeNode]] = {}
    for m in all_methods:
        # Find enclosing class node in the same file
        for c_id, c_node in class_node_map.items():
            if c_node.file == m.file and m.name.startswith(f"{c_node.name}."):
                class_methods_map.setdefault(c_id, []).append(m)
                break

    for sub_class_id, sub_methods in class_methods_map.items():
        if sub_class_id not in ancestry_graph:
            continue

        # Transitive ancestry of this subclass
        ancestor_ids = nx.descendants(ancestry_graph, sub_class_id)
        for ancestor_id in ancestor_ids:
            super_methods = class_methods_map.get(ancestor_id, [])
            super_methods_by_name: Dict[str, List[CodeNode]] = {}
            for base_m in super_methods:
                leaf = base_m.name.split(".")[-1]
                super_methods_by_name.setdefault(leaf, []).append(base_m)

            for sm in sub_methods:
                m_leaf = sm.name.split(".")[-1]
                matching_base_candidates = super_methods_by_name.get(m_leaf, [])
                for base_method in matching_base_candidates:
                    # Verify signature compatibility
                    is_compatible = check_signature_compatibility(sm.signature, base_method.signature)
                    if not is_compatible:
                        logger.debug(
                            f"Skipping incompatible override: {sm.name}{sm.signature} vs {base_method.name}{base_method.signature}"
                        )
                        continue

                    ov_attrs = {
                        "edge_type": EdgeType.E_OVERRIDE.value,
                        "confidence": 1.0,
                        "method": m_leaf,
                        "sub_method": sm.name,
                        "base_method": base_method.name,
                        "sub_method_sig": sm.signature,
                        "base_method_sig": base_method.signature,
                        "qualified_sub_method": sm.qualified_name or sm.name,
                        "qualified_base_method": base_method.qualified_name or base_method.name,
                        "signature_compatible": True
                    }
                    if graph.is_multigraph():
                        ov_key = f"{EdgeType.E_OVERRIDE.value}:{sub_class_id}:{sm.node_id}:{base_method.node_id}"
                        graph.add_edge(sm.node_id, base_method.node_id, key=ov_key, **ov_attrs)
                    else:
                        graph.add_edge(sm.node_id, base_method.node_id, **ov_attrs)
                    resolved_count += 1

    logger.info(f"Resolved {resolved_count} inheritance & override edges")
    return resolved_count
