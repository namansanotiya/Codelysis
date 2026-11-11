"""
Import Relationship Edges (E_import) Module.
Connects importing files/scopes to imported modules and exported symbol definitions.
Supports:
  - Python absolute imports, relative imports (`.`, `..`), aliases, and __init__.py packages
  - JavaScript/TypeScript relative paths (`./`, `../`), extensions (.js, .ts, .jsx, .tsx, /index)
  - Strict package-aware resolution without broad suffix-based false matches
  - Distinguishing internal repo targets from external packages
  - MultiDiGraph edge representation with confidence and metadata
"""
import os
import logging
from typing import Dict, List, Set, Optional, Union
import networkx as nx
from core.types import CodeNode, ImportBinding, EdgeType
from parsers.filter import is_builtin_or_stdlib

logger = logging.getLogger("import_edges")


def resolve_relative_python_path(module: str, importing_file: str, all_files: Set[str]) -> Optional[str]:
    """
    Resolve Python relative import such as 'from . import bar' or 'from ..core import types'.
    """
    clean_importer = importing_file.replace("\\", "/")
    importer_dir = os.path.dirname(clean_importer)
    
    # Count leading dots
    dots = len(module) - len(module.lstrip('.'))
    if dots == 0:
        return None
    
    remainder = module[dots:].replace(".", "/")
    
    # Navigate up (dots - 1) levels from importer_dir
    curr = importer_dir
    for _ in range(dots - 1):
        curr = os.path.dirname(curr)
        
    candidate_base = os.path.join(curr, remainder) if remainder else curr
    candidate_base = candidate_base.replace("\\", "/").rstrip("/")
    
    # Try direct .py or package __init__.py
    for cand in [f"{candidate_base}.py", f"{candidate_base}/__init__.py", candidate_base]:
        if cand in all_files:
            return cand
            
    return None


def resolve_js_module_path(module: str, importing_file: str, all_files: Set[str]) -> Optional[str]:
    """
    Resolve JS/TS relative imports like './authService' or '../utils/format'.
    """
    clean_importer = importing_file.replace("\\", "/")
    importer_dir = os.path.dirname(clean_importer)
    
    if not (module.startswith("./") or module.startswith("../")):
        # Non-relative import in JS/TS is typically node_modules / external
        return None
        
    target_base = os.path.normpath(os.path.join(importer_dir, module)).replace("\\", "/")
    
    # Check exact match or known extensions
    extensions = ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js", "/index.jsx"]
    for ext in extensions:
        cand = f"{target_base}{ext}"
        if cand in all_files:
            return cand
            
    return None


def resolve_import_edges(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    file_imports: Dict[str, List[ImportBinding]],
    file_nodes: Dict[str, CodeNode],
    symbol_defs: Dict[str, List[CodeNode]],
) -> int:
    """
    Resolve and wire E_import edges from importing files to imported files and symbols.
    Avoids broad suffix false matches by enforcing strict package structure and context.
    Returns the count of successfully resolved internal import edges.
    """
    resolved_count = 0
    all_repo_files: Set[str] = set(file_nodes.keys())

    # Build python module-to-file lookup: e.g. "auth.token" -> "auth/token.py"
    module_to_file: Dict[str, str] = {}
    for rel_path in all_repo_files:
        clean_path = rel_path.replace("\\", "/")
        no_ext, _ = os.path.splitext(clean_path)
        mod_key = no_ext.replace("/", ".").strip(".")
        module_to_file[mod_key] = rel_path
        
        # Also index directory packages with __init__.py
        if clean_path.endswith("/__init__.py"):
            pkg_mod = os.path.dirname(clean_path).replace("/", ".").strip(".")
            if pkg_mod:
                module_to_file[pkg_mod] = rel_path

    for rel_path, bindings in file_imports.items():
        importer_node = file_nodes.get(rel_path)
        if not importer_node:
            continue
        importer_id = importer_node.node_id
        importer_dir = os.path.dirname(rel_path.replace("\\", "/"))

        for b in bindings:
            target_rel_path: Optional[str] = None
            is_external = False

            # Case A: Python relative import (starts with '.')
            if b.module.startswith("."):
                target_rel_path = resolve_relative_python_path(b.module, rel_path, all_repo_files)

            # Case B: JS/TS relative import (starts with './' or '../')
            elif b.module.startswith("./") or b.module.startswith("../"):
                target_rel_path = resolve_js_module_path(b.module, rel_path, all_repo_files)

            # Case C: Absolute / Qualified module import
            else:
                # 1. Exact module match
                if b.module in module_to_file:
                    target_rel_path = module_to_file[b.module]

                # 2. Local sibling package match: check if b.module is located in importer's own directory
                if not target_rel_path and importer_dir:
                    local_mod_key = f"{importer_dir.replace('/', '.')}.{b.module}".strip(".")
                    if local_mod_key in module_to_file:
                        target_rel_path = module_to_file[local_mod_key]

                # 3. Top-level repo root prefix match (e.g. root_dir.pkg.mod when import is pkg.mod)
                # Removes unsafe broad suffix-based matching by requiring exact structural match
                if not target_rel_path and b.module:
                    mod_parts = b.module.split(".")
                    top_level_matches = []
                    for mod_k, f_path in module_to_file.items():
                        parts = mod_k.split(".")
                        if len(parts) == len(mod_parts) + 1 and parts[1:] == mod_parts:
                            top_level_matches.append((mod_k, f_path))

                    if len(top_level_matches) == 1:
                        target_rel_path = top_level_matches[0][1]
                    elif len(top_level_matches) > 1:
                        importer_top = rel_path.replace("\\", "/").split("/")[0]
                        filtered = [fp for mk, fp in top_level_matches if mk.split(".")[0] == importer_top]
                        if len(filtered) == 1:
                            target_rel_path = filtered[0]
                        else:
                            logger.debug(
                                f"Ambiguous import '{b.module}' in {rel_path} matched multiple root targets: {top_level_matches}"
                            )
                            target_rel_path = None

                # 4. Check if external / standard library
                if not target_rel_path:
                    top_pkg = b.module.split(".")[0].split("/")[0]
                    if is_builtin_or_stdlib(top_pkg, "python") or is_builtin_or_stdlib(top_pkg, "javascript"):
                        is_external = True
                    else:
                        is_external = True

            # If external and not in repo, do not create false internal edges
            if is_external and not target_rel_path:
                continue

            # 1. Wire file-level E_import edge
            if target_rel_path and target_rel_path in file_nodes:
                target_file_node = file_nodes[target_rel_path]
                if target_file_node.node_id != importer_id:
                    edge_attrs = {
                        "edge_type": EdgeType.E_IMPORT.value,
                        "confidence": 1.0,
                        "module": b.module,
                        "symbol": b.symbol,
                        "alias": b.alias,
                        "line": b.line,
                        "is_external": False
                    }
                    if graph.is_multigraph():
                        key = f"{EdgeType.E_IMPORT.value}:{target_rel_path}"
                        graph.add_edge(importer_id, target_file_node.node_id, key=key, **edge_attrs)
                    else:
                        graph.add_edge(importer_id, target_file_node.node_id, **edge_attrs)
                    resolved_count += 1

            # 2. If it's a specific symbol import (`from mod import sym`), connect to symbol definition
            if b.is_from_import and b.symbol and b.symbol != "*":
                candidate_defs = symbol_defs.get(b.symbol, [])
                for def_node in candidate_defs:
                    # Connect if candidate belongs to the resolved target file
                    if target_rel_path and def_node.file == target_rel_path:
                        edge_attrs = {
                            "edge_type": EdgeType.E_IMPORT.value,
                            "confidence": 1.0,
                            "module": b.module,
                            "symbol": b.symbol,
                            "alias": b.alias,
                            "line": b.line,
                            "is_external": False
                        }
                        if graph.is_multigraph():
                            key = f"{EdgeType.E_IMPORT.value}:{b.symbol}:{def_node.node_id}"
                            graph.add_edge(importer_id, def_node.node_id, key=key, **edge_attrs)
                        else:
                            graph.add_edge(importer_id, def_node.node_id, **edge_attrs)
                        resolved_count += 1

    logger.info(f"Resolved {resolved_count} E_import edges across {len(file_imports)} files")
    return resolved_count
