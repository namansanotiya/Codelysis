"""
Repository Graph Builder (RepoGraph ICLR 2025).
Coordinates parsing across source files and wires E_contain and E_invoke edges into G = (V, E).
"""
import os
import logging
from typing import Dict, List, Tuple, Optional, Set, Union
import networkx as nx

from core.types import CodeNode, Category, NodeType
from parsers.factory import ParserFactory
from parsers.filter import extract_third_party_imports
from graph.container_edges import add_containment_edge
from graph.invocation_edges import resolve_invocation_edges

logger = logging.getLogger("graph_builder")


class RepoGraphBuilder:
    """
    Constructs a directed line & symbol dependency graph G = (V, E).
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.symbol_defs: Dict[str, List[CodeNode]] = {}
        self.file_nodes: Dict[str, CodeNode] = {}
        self.all_references: List[Tuple[str, CodeNode, Optional[str]]] = []
        self.third_party_symbols: Set[str] = set()

    def build_from_files(self, file_contents: Dict[str, str]) -> nx.DiGraph:
        """
        Build graph from in-memory dictionary of {relative_file_path: file_content}.
        Used by both local filesystem loaders and GitHub API source loaders.
        """
        self.graph.clear()
        self.symbol_defs.clear()
        self.file_nodes.clear()
        self.all_references.clear()
        self.third_party_symbols.clear()

        logger.info(f"Building RepoGraph for {len(file_contents)} files...")

        # Pass 1: Parse definitions and references per file
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
                snippet=lines[0].strip() if lines else ""
            )
            self.file_nodes[rel_path] = file_node
            self.graph.add_node(file_node_id, **file_node.to_dict())

            # Step 2: Filter 3rd party imports (RepoGraph Step 2: Local relation filtering)
            local_third_party = extract_third_party_imports(content)
            self.third_party_symbols.update(local_third_party)

            # Step 3: Parse language symbols
            parser = ParserFactory.get_parser(rel_path)
            defs, refs = parser.parse(rel_path, content)

            # Register definition nodes and E_contain from File to Top-Level Defs
            for def_node in defs:
                self.graph.add_node(def_node.node_id, **def_node.to_dict())
                self.symbol_defs.setdefault(def_node.name, []).append(def_node)
                
                # Index short name if qualified (e.g., Class.method -> method)
                if "." in def_node.name:
                    short = def_node.name.split(".")[-1]
                    self.symbol_defs.setdefault(short, []).append(def_node)
                elif "::" in def_node.name:
                    short = def_node.name.split("::")[-1]
                    self.symbol_defs.setdefault(short, []).append(def_node)

                # Connect File -> Definition
                add_containment_edge(self.graph, file_node_id, def_node.node_id)

            # Register reference call sites
            for ref_node, enc_id in refs:
                self.graph.add_node(ref_node.node_id, **ref_node.to_dict())
                parent_id = enc_id or file_node_id
                add_containment_edge(self.graph, parent_id, ref_node.node_id)
                self.all_references.append((rel_path, ref_node, parent_id))

        # Pass 2: Resolve invocation edges (E_invoke)
        resolved = resolve_invocation_edges(
            self.graph,
            self.all_references,
            self.symbol_defs,
            ignored_symbols=self.third_party_symbols
        )

        logger.info(
            f"RepoGraph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges ({resolved} invocations resolved)."
        )
        return self.graph


def build_graph(source_input: Union[str, Dict[str, str]]) -> nx.DiGraph:
    """
    Convenience wrapper: accepts local path string OR dictionary of {rel_path: content}.
    """
    builder = RepoGraphBuilder()
    if isinstance(source_input, dict):
        return builder.build_from_files(source_input)
    
    # Load from local directory
    from sources.local_loader import LocalLoader
    loader = LocalLoader(source_input)
    files = loader.load_all_files()
    return builder.build_from_files(files)
