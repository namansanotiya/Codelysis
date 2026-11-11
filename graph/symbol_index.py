"""
Centralized Symbol Index for scoped, qualified-name-aware symbol resolution.

Replaces the flat `Dict[str, List[CodeNode]]` in graph/builder.py with a
structured index that tracks:
  - Definitions by qualified name, short name, and file
  - Import alias chains per file
  - Class inheritance metadata

Resolution tier hierarchy (matches invocation_edges.py confidence model):
  1. Exact qualified-name match (intra-class self/this, 1.00)
  2. Import/alias-resolved exact match (0.95)
  3. Same-file local definition match (0.95)
  4. Module-attribute receiver match (0.90)
  5. Same-directory sibling module match (0.70)
  6. Repo-wide unique match (0.50) / ambiguous fallback (0.35)
  7. UNRESOLVED — no edge created

Design principle: never connect two nodes based on short-name coincidence alone
when the short name is ambiguous across files.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Set
from core.types import CodeNode, ImportBinding

logger = logging.getLogger("symbol_index")


class SymbolIndex:
    """
    Structured index of all definition-site CodeNodes across a repository.

    Usage:
        idx = SymbolIndex()
        idx.add_definition(node)
        idx.add_imports("auth/service.py", [ImportBinding(...)])
        candidates = idx.resolve("validate", from_file="api/router.py", scope="Router.handle")
    """

    def __init__(self):
        # Primary indexes
        self.by_qualified_name: Dict[str, List[CodeNode]] = {}   # "auth.service.validate" -> [node]
        self.by_short_name: Dict[str, List[CodeNode]] = {}        # "validate" -> [node, ...]
        self.by_file: Dict[str, List[CodeNode]] = {}              # "auth/service.py" -> [node, ...]

        # Import alias map per file: file_path -> {local_alias -> ImportBinding}
        self.import_aliases: Dict[str, Dict[str, ImportBinding]] = {}

        # Module path -> file path (for receiver resolution)
        self.module_to_file: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add_definition(self, node: CodeNode) -> None:
        """Index a definition-site CodeNode by qualified name, short name, and file."""
        # Short name (leaf of dotted name)
        short = node.name.split(".")[-1] if "." in node.name else node.name
        if "::" in node.name:
            short = node.name.split("::")[-1]

        # Qualified name (use pre-computed if available)
        qname = node.qualified_name or node.name

        self.by_qualified_name.setdefault(qname, []).append(node)
        self.by_short_name.setdefault(short, []).append(node)
        self.by_file.setdefault(node.file, []).append(node)

        # Also index the full dotted name (Class.method) under short name
        if node.name != short:
            self.by_short_name.setdefault(node.name, []).append(node)

        # Build module -> file mapping
        clean = node.file.replace("\\", "/")
        no_ext, _ = os.path.splitext(clean)
        mod_key = no_ext.replace("/", ".").strip(".")
        self.module_to_file[mod_key] = node.file

    def add_imports(self, file_path: str, bindings: List[ImportBinding]) -> None:
        """Register import alias bindings for a file."""
        alias_map = self.import_aliases.setdefault(file_path, {})
        for b in bindings:
            alias_map[b.alias] = b

    def bulk_add(self, nodes: List[CodeNode]) -> None:
        """Add multiple definition nodes at once."""
        for n in nodes:
            self.add_definition(n)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(
        self,
        name: str,
        from_file: str,
        scope: str = "",
        receiver: Optional[str] = None,
    ) -> List[Tuple[CodeNode, float, str]]:
        """
        Resolve a called symbol to definition-site nodes with confidence scores.

        Returns a list of (CodeNode, confidence, resolution_method) tuples,
        sorted by descending confidence. Returns [] when unresolvable.

        Parameters
        ----------
        name       : Called symbol (may be a short name, alias, or qualified name).
        from_file  : File path of the call site.
        scope      : Enclosing scope qualified name (e.g., "MyClass.my_method").
        receiver   : Receiver expression (e.g., "self", "cls", "my_obj").
        """
        results: List[Tuple[CodeNode, float, str]] = []
        alias_map = self.import_aliases.get(from_file, {})

        # ------------------------------------------------------------------
        # Tier 1: Intra-class self/this/cls.method (1.00)
        # Supports multi-level class nesting e.g. Outer.Inner.method
        # ------------------------------------------------------------------
        if receiver in ("self", "this", "cls") and scope:
            parts = scope.split(".")
            for i in range(len(parts), 0, -1):
                enclosing_class = ".".join(parts[:i])
                qualified_method = f"{enclosing_class}.{name}"
                for node in self.by_short_name.get(qualified_method, []):
                    if node.file == from_file:
                        results.append((node, 1.00, "intra_class"))
                if results:
                    return results

        # ------------------------------------------------------------------
        # Tier 2: Directly imported symbol / alias (0.95)
        # ------------------------------------------------------------------
        if name in alias_map:
            binding = alias_map[name]
            real_symbol = binding.symbol or name
            # Try matching by qualified module + symbol name
            for node in self.by_short_name.get(real_symbol, []):
                node_mod = os.path.splitext(node.file.replace("\\", "/"))[0].replace("/", ".").strip(".")
                if binding.module and (
                    node_mod.endswith(binding.module) or binding.module.endswith(node_mod)
                ):
                    results.append((node, 0.95, "import_exact"))
            if not results:
                # Module found but no exact symbol match; lower confidence
                for node in self.by_short_name.get(real_symbol, []):
                    results.append((node, 0.90, "import_fallback"))
            if results:
                return self._deduplicated(results)

        # ------------------------------------------------------------------
        # Tier 3: Module-attribute receiver call  mod.name()  (0.90)
        # ------------------------------------------------------------------
        if receiver and receiver in alias_map and not results:
            binding = alias_map[receiver]
            target_file = self.module_to_file.get(binding.module)
            for node in self.by_short_name.get(name, []):
                if not target_file or node.file == target_file:
                    results.append((node, 0.90, "module_attr"))
            if results:
                return self._deduplicated(results)

        # ------------------------------------------------------------------
        # Tier 4: Lexical scope & same-file local definition (0.95)
        # Searches from innermost enclosing scope outwards, preserving lexical hierarchy
        # ------------------------------------------------------------------
        if not results and scope:
            parts = scope.split(".")
            for i in range(len(parts), 0, -1):
                parent = ".".join(parts[:i])
                scoped_name = f"{parent}.{name}"
                for node in self.by_short_name.get(scoped_name, []):
                    if node.file == from_file:
                        results.append((node, 0.95, "lexical_scope_exact"))
                if results:
                    return self._deduplicated(results)

        if not results:
            for node in self.by_file.get(from_file, []):
                if node.name == name or node.name.endswith(f".{name}"):
                    results.append((node, 0.95, "local_exact"))
            if results:
                return self._deduplicated(results)

        # ------------------------------------------------------------------
        # Tier 5: Same-directory sibling module (0.70)
        # ------------------------------------------------------------------
        if not results:
            current_dir = os.path.dirname(from_file.replace("\\", "/"))
            for node in self.by_short_name.get(name, []):
                node_dir = os.path.dirname(node.file.replace("\\", "/"))
                if node_dir == current_dir:
                    results.append((node, 0.70, "sibling_module"))
            if results:
                return self._deduplicated(results)

        # ------------------------------------------------------------------
        # Tier 6: Repo-wide fallback (0.50 unique / 0.35 ambiguous)
        # ------------------------------------------------------------------
        if not results:
            candidates = self.by_short_name.get(name, [])
            if candidates:
                conf = 0.50 if len(candidates) == 1 else 0.35
                method = "repo_unique" if len(candidates) == 1 else "repo_ambiguous"
                for node in candidates:
                    results.append((node, conf, method))

        return self._deduplicated(results)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _deduplicated(self, results: List[Tuple[CodeNode, float, str]]) -> List[Tuple[CodeNode, float, str]]:
        """Remove duplicate node_id entries, keeping highest confidence."""
        seen: Dict[str, Tuple[CodeNode, float, str]] = {}
        for node, conf, method in results:
            if node.node_id not in seen or conf > seen[node.node_id][1]:
                seen[node.node_id] = (node, conf, method)
        return sorted(seen.values(), key=lambda x: x[1], reverse=True)

    def get_definitions_in_file(self, file_path: str) -> List[CodeNode]:
        """Return all definition nodes in a given file."""
        return self.by_file.get(file_path, [])

    def get_by_name(self, name: str) -> List[CodeNode]:
        """Return all definitions with this short or dotted name."""
        return self.by_short_name.get(name, [])

    def stats(self) -> Dict[str, int]:
        return {
            "total_definitions": sum(len(v) for v in self.by_file.values()),
            "unique_qualified_names": len(self.by_qualified_name),
            "unique_short_names": len(self.by_short_name),
            "files_indexed": len(self.by_file),
        }

