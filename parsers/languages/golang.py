"""
Go (Golang) Source Parser.
Extracts structs, interfaces, functions, receiver methods, and call sites.
"""
import re
from typing import List, Tuple, Optional
from core.types import CodeNode
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


class GoParser(BaseParser):
    def __init__(self):
        self.type_re = re.compile(r"^\s*type\s+([A-Za-z0-9_]+)\s+(?:struct|interface)")
        self.method_re = re.compile(
            r"^\s*func\s*\(\s*(?:\w+\s+)?\*?([A-Za-z0-9_]+)\s*\)\s*([A-Za-z0-9_]+)\s*\("
        )
        self.func_re = re.compile(r"^\s*func\s+([A-Za-z0-9_]+)\s*\(")
        self.call_re = re.compile(r"\b([A-Za-z0-9_]+)\s*\(")

    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        source_lines = content.splitlines()
        definitions: List[CodeNode] = []
        references: List[Tuple[CodeNode, Optional[str]]] = []
        current_container: Optional[CodeNode] = None

        for idx, line_str in enumerate(source_lines, start=1):
            clean = line_str.strip()
            if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*"):
                continue

            # 1. Struct / Interface definition
            type_match = self.type_re.search(clean)
            if type_match:
                tname = type_match.group(1)
                if not is_builtin_or_stdlib(tname, "golang"):
                    node_id = f"{file_path}:L{idx}:def:{tname}"
                    tnode = CodeNode(node_id, file_path, idx, tname, "def", "struct", clean)
                    definitions.append(tnode)
                    current_container = tnode
                    continue

            # 2. Receiver Method
            method_match = self.method_re.search(clean)
            if method_match:
                rec_name = method_match.group(1)
                mname = method_match.group(2)
                if not is_builtin_or_stdlib(mname, "golang"):
                    full_name = f"{rec_name}.{mname}"
                    node_id = f"{file_path}:L{idx}:def:{full_name}"
                    mnode = CodeNode(node_id, file_path, idx, full_name, "def", "method", clean)
                    definitions.append(mnode)
                    current_container = mnode
                    continue

            # 3. Standard Function
            func_match = self.func_re.search(clean)
            if func_match:
                fname = func_match.group(1)
                if not is_builtin_or_stdlib(fname, "golang"):
                    node_id = f"{file_path}:L{idx}:def:{fname}"
                    fnode = CodeNode(node_id, file_path, idx, fname, "def", "function", clean)
                    definitions.append(fnode)
                    current_container = fnode

            # 4. Call sites
            for call_match in self.call_re.finditer(clean):
                called = call_match.group(1)
                if not is_builtin_or_stdlib(called, "golang"):
                    enclosing = current_container
                    if not enclosing or enclosing.name.split(".")[-1] != called:
                        ref_id = f"{file_path}:L{idx}:ref:{called}"
                        ref_node = CodeNode(ref_id, file_path, idx, called, "ref", "call", clean)
                        references.append((ref_node, enclosing.node_id if enclosing else None))

        return definitions, references
