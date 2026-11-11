"""
Repository Graph Builder (RepoGraph ICLR 2025 & Codelysis Extension).
Coordinates multi-language parsing across source files and wires E_contain, E_invoke,
E_import, E_inherit, and E_override edges into MultiDiGraph G = (V, E).

Edge direction convention (verified against RepoGraph ICLR 2025, Section 3):
  E_contain : container_node -> contained_node  (file->class, class->method, func->call)
  E_invoke  : ref_site_node  -> def_site_node   (call site -> callee definition)
  E_import  : importing_file -> imported_target  (importer -> importee)
  E_inherit : subclass       -> superclass       (child -> parent)
  E_override: overriding_method -> overridden_base_method
  E_implement: concrete_class -> interface/abstract
"""
import os
import logging
from typing import Dict, List, Tuple, Optional, Set, Union
import networkx as nx

from core.types import CodeNode, Category, NodeType, ImportBinding
from parsers.factory import ParserFactory
from parsers.filter import extract_third_party_imports
from graph.container_edges import add_containment_edge
from graph.invocation_edges import resolve_invocation_edges
from graph.import_edges import resolve_import_edges
from graph.inheritance_edges import resolve_inheritance_edges
from graph.symbol_index import SymbolIndex

logger = logging.getLogger("graph_builder")


class RepoGraphBuilder:
    """
    Constructs a directed line & symbol dependency graph G = (V, E).
    Defaults to nx.MultiDiGraph to support multi-relational edges between
    the same pair of nodes (e.g. E_contain + E_invoke on the same pair).
    """

    def __init__(self, multigraph: bool = True):
        self.multigraph = multigraph
        self.graph: Union[nx.MultiDiGraph, nx.DiGraph] = nx.MultiDiGraph() if multigraph else nx.DiGraph()
        # Centralized symbol index (replaces flat Dict[str, List[CodeNode]])
        self.symbol_index: SymbolIndex = SymbolIndex()
        # Backward-compat alias kept for edge resolvers that still accept symbol_defs dict
        self.symbol_defs: Dict[str, List[CodeNode]] = {}
        self.file_nodes: Dict[str, CodeNode] = {}
        self.all_references: List[Tuple[str, CodeNode, Optional[str]]] = []
        self.file_imports: Dict[str, List[ImportBinding]] = {}
        self.class_bases: Dict[str, List[str]] = {}
        self.third_party_symbols: Set[str] = set()

    def build_from_files(self, file_contents: Dict[str, str]) -> Union[nx.MultiDiGraph, nx.DiGraph]:
        """
        Build graph from in-memory dictionary of {relative_file_path: file_content}.
        Used by both local filesystem loaders and GitHub API source loaders.
        """
        self.graph.clear()
        self.symbol_index = SymbolIndex()
        self.symbol_defs.clear()
        self.file_nodes.clear()
        self.all_references.clear()
        self.file_imports.clear()
        self.class_bases.clear()
        self.third_party_symbols.clear()

        logger.info(f"Building RepoGraph for {len(file_contents)} files (MultiGraph={self.multigraph})...")

        # ======================================================================
        # Pass 1: Parse definitions, references, imports, and bases per file
        # ======================================================================
        for rel_path, content in file_contents.items():
            lines = content.splitlines()
            filename = os.path.basename(rel_path)

            # Step 1: Register File Node
            file_node_id = f"{rel_path}:L1:def:{filename}"
            file_node = CodeNode(
                node_id=file_node_id,
                file=rel_path,
                line=1,
                name=filename,
                type=NodeType.DEF.value,
                category=Category.FILE.value,
                end_line=len(lines) if lines else 1,
                snippet=lines[0].strip() if lines else ""
            )
            self.file_nodes[rel_path] = file_node
            self.graph.add_node(file_node_id, **file_node.to_dict())

            # Step 2: Filter 3rd party imports (RepoGraph Step 2: Local relation filtering)
            local_third_party = extract_third_party_imports(content)
            self.third_party_symbols.update(local_third_party)

            # Step 3: Parse language symbols & metadata
            parser = ParserFactory.get_parser(rel_path)
            defs, refs = parser.parse(rel_path, content)

            # Collect imports and inheritance from parser if available
            parsed_imports = parser.get_imports()
            if parsed_imports:
                self.file_imports[rel_path] = parsed_imports
                # Register imports into the SymbolIndex for alias resolution
                self.symbol_index.add_imports(rel_path, parsed_imports)

            # Collect class bases keyed by unique node_id to prevent duplicate class names from colliding
            for def_node in defs:
                if def_node.category in (Category.CLASS.value, Category.STRUCT.value, Category.INTERFACE.value):
                    bases = def_node.metadata.get("bases", [])
                    if bases:
                        self.class_bases[def_node.node_id] = bases

            parsed_bases = parser.get_class_bases()
            if parsed_bases:
                for k, v in parsed_bases.items():
                    if ":" in k:
                        self.class_bases[k] = v

            # Register definition nodes and lexical E_contain edges
            for def_node in defs:
                self.graph.add_node(def_node.node_id, **def_node.to_dict())

                # Add to both SymbolIndex and backward-compat dict
                self.symbol_index.add_definition(def_node)
                self.symbol_defs.setdefault(def_node.name, []).append(def_node)

                # Index short name if qualified (e.g., Class.method -> method)
                if "." in def_node.name:
                    short = def_node.name.split(".")[-1]
                    self.symbol_defs.setdefault(short, []).append(def_node)
                elif "::" in def_node.name:
                    short = def_node.name.split("::")[-1]
                    self.symbol_defs.setdefault(short, []).append(def_node)

                # Lexical containment: If def_node is nested inside an enclosing definition in the same file,
                # wire parent_definition -> def_node; otherwise wire file_node -> def_node
                container_id = file_node_id
                if def_node.parent_scope:
                    for potential_parent in defs:
                        if potential_parent.name == def_node.parent_scope and potential_parent.node_id != def_node.node_id:
                            container_id = potential_parent.node_id
                            break
                add_containment_edge(self.graph, container_id, def_node.node_id)

            # Register reference call sites
            for ref_node, enc_id in refs:
                self.graph.add_node(ref_node.node_id, **ref_node.to_dict())
                parent_id = enc_id or file_node_id
                add_containment_edge(self.graph, parent_id, ref_node.node_id)
                self.all_references.append((rel_path, ref_node, parent_id))

        logger.info(f"SymbolIndex: {self.symbol_index.stats()}")

        # ======================================================================
        # Pass 2: Wire Import relationships (E_import)
        # ======================================================================
        resolved_imports = resolve_import_edges(
            self.graph,
            self.file_imports,
            self.file_nodes,
            self.symbol_defs
        )

        # ======================================================================
        # Pass 3: Wire Inheritance & Overrides (E_inherit, E_override, E_implement)
        # ======================================================================
        resolved_inherits = resolve_inheritance_edges(
            self.graph,
            self.class_bases,
            self.symbol_defs,
            file_imports=self.file_imports,
            symbol_index=self.symbol_index
        )

        # ======================================================================
        # Pass 4: Resolve scoped invocation edges (E_invoke)
        # Uses SymbolIndex for proper scoped resolution; falls back to symbol_defs.
        # ======================================================================
        resolved_invokes = resolve_invocation_edges(
            self.graph,
            self.all_references,
            self.symbol_defs,
            file_imports=self.file_imports,
            class_bases=self.class_bases,
            ignored_symbols=self.third_party_symbols,
            symbol_index=self.symbol_index
        )

        logger.info(
            f"RepoGraph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges "
            f"({resolved_invokes} calls, {resolved_imports} imports, {resolved_inherits} inherits/overrides)."
        )
        return self.graph


def build_graph(source_input: Union[str, Dict[str, str]], multigraph: bool = True) -> Union[nx.MultiDiGraph, nx.DiGraph]:
    """
    Convenience wrapper: accepts local path string OR dictionary of {rel_path: content}.
    Defaults to MultiDiGraph to support multi-relational edges.
    """
    builder = RepoGraphBuilder(multigraph=multigraph)
    if isinstance(source_input, dict):
        return builder.build_from_files(source_input)

    # Load from local directory
    from sources.local_loader import LocalLoader
    loader = LocalLoader(source_input)
    files = loader.load_all_files()
    return builder.build_from_files(files)
