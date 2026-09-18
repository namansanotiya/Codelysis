"""
Java and Kotlin Parser.
Extracts classes, interfaces, methods, and method invocations.
"""
import re
from typing import List, Tuple, Optional
from core.types import CodeNode
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


class JavaParser(BaseParser):
    def __init__(self):
        self.class_re = re.compile(
            r"^\s*(?:(?:public|private|protected|abstract|final|static)\s+)*(?:class|interface|enum|record)\s+([A-Za-z0-9_]+)"
        )
        self.method_re = re.compile(
            r"^\s*(?:(?:public|private|protected|abstract|static|final|synchronized|native|default)\s+)*"
            r"(?:<[^>]+>\s+)?(?:[\w<>\[\],\s\?]+)\s+([A-Za-z0-9_]+)\s*\([^;{]*\)\s*(?:throws\s+[\w,\s]+)?\{"
        )
        self.call_re = re.compile(r"\b([A-Za-z0-9_]+)\s*\(")

    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        source_lines = content.splitlines()
        definitions: List[CodeNode] = []
        references: List[Tuple[CodeNode, Optional[str]]] = []
        current_class: Optional[CodeNode] = None
        current_method: Optional[CodeNode] = None

        for idx, line_str in enumerate(source_lines, start=1):
            clean = line_str.strip()
            if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*") or clean.startswith("@"):
                continue

            # 1. Class / Interface / Enum
            class_match = self.class_re.search(clean)
            if class_match:
                cname = class_match.group(1)
                if not is_builtin_or_stdlib(cname, "java"):
                    node_id = f"{file_path}:L{idx}:def:{cname}"
                    cnode = CodeNode(node_id, file_path, idx, cname, "def", "class", clean)
                    definitions.append(cnode)
                    current_class = cnode
                    current_method = None
                    continue

            # 2. Method
            method_match = self.method_re.search(clean)
            if method_match:
                mname = method_match.group(1)
                if not is_builtin_or_stdlib(mname, "java"):
                    full_name = f"{current_class.name}.{mname}" if current_class else mname
                    node_id = f"{file_path}:L{idx}:def:{full_name}"
                    mnode = CodeNode(node_id, file_path, idx, full_name, "def", "method", clean)
                    definitions.append(mnode)
                    current_method = mnode

            # 3. Call sites
            for call_match in self.call_re.finditer(clean):
                called = call_match.group(1)
                if not is_builtin_or_stdlib(called, "java"):
                    enclosing = current_method or current_class
                    if not enclosing or enclosing.name.split(".")[-1] != called:
                        ref_id = f"{file_path}:L{idx}:ref:{called}"
                        ref_node = CodeNode(ref_id, file_path, idx, called, "ref", "call", clean)
                        references.append((ref_node, enclosing.node_id if enclosing else None))

        return definitions, references
