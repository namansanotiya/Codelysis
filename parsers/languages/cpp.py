"""
C and C++ Source Parser.
Extracts classes, structs, functions, methods, and call sites.
"""
import re
from typing import List, Tuple, Optional
from core.types import CodeNode
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


class CppParser(BaseParser):
    def __init__(self):
        self.class_re = re.compile(r"^\s*(?:class|struct)\s+([A-Za-z0-9_]+)\s*(?::\s*[^{]+)?\{")
        self.func_re = re.compile(
            r"^\s*(?:inline\s+|static\s+|virtual\s+|explicit\s+|constexpr\s+)*"
            r"(?:[\w:*&<>\s]+)\s+([A-Za-z0-9_]+)\s*\([^;{]*\)\s*(?:const\s*)?\{"
        )
        self.call_re = re.compile(r"\b([A-Za-z0-9_]+)\s*\(")

    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        source_lines = content.splitlines()
        definitions: List[CodeNode] = []
        references: List[Tuple[CodeNode, Optional[str]]] = []
        current_container: Optional[CodeNode] = None

        for idx, line_str in enumerate(source_lines, start=1):
            clean = line_str.strip()
            if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*") or clean.startswith("#"):
                continue

            # 1. Class or Struct definition
            class_match = self.class_re.search(clean)
            if class_match:
                cname = class_match.group(1)
                if not is_builtin_or_stdlib(cname, "cpp"):
                    node_id = f"{file_path}:L{idx}:def:{cname}"
                    cnode = CodeNode(node_id, file_path, idx, cname, "def", "class", clean)
                    definitions.append(cnode)
                    current_container = cnode
                    continue

            # 2. Function or Method definition
            func_match = self.func_re.search(clean)
            if func_match:
                fname = func_match.group(1)
                if not is_builtin_or_stdlib(fname, "cpp"):
                    category = "method" if current_container and current_container.category == "class" else "function"
                    full_name = f"{current_container.name}::{fname}" if category == "method" else fname
                    node_id = f"{file_path}:L{idx}:def:{full_name}"
                    fnode = CodeNode(node_id, file_path, idx, full_name, "def", category, clean)
                    definitions.append(fnode)
                    current_container = fnode

            # 3. Call sites
            for call_match in self.call_re.finditer(clean):
                called = call_match.group(1)
                if not is_builtin_or_stdlib(called, "cpp"):
                    enclosing = current_container
                    if not enclosing or enclosing.name.split("::")[-1] != called:
                        ref_id = f"{file_path}:L{idx}:ref:{called}"
                        ref_node = CodeNode(ref_id, file_path, idx, called, "ref", "call", clean)
                        references.append((ref_node, enclosing.node_id if enclosing else None))

        return definitions, references
