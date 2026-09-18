"""
JavaScript and TypeScript Parser (ES6+, TS, JSX, TSX).
Extracts classes, functions, arrow functions, methods, and call invocations.
"""
import re
from typing import List, Tuple, Optional
from core.types import CodeNode
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


class JavaScriptParser(BaseParser):
    def __init__(self):
        self.class_re = re.compile(
            r"^\s*(?:export\s+(?:default\s+)?)?class\s+([A-Za-z0-9_$]+)"
        )
        self.func_re = re.compile(
            r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function(?:\s+([A-Za-z0-9_$]+))?\s*\("
        )
        self.arrow_or_assigned_func_re = re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>"
        )
        self.method_re = re.compile(
            r"^\s*(?:(?:public|private|protected|static|async)\s+)*([A-Za-z0-9_$]+)\s*\([^)]*\)\s*(?::\s*[\w<>\[\]]+\s*)?\{"
        )
        self.call_re = re.compile(r"\b([A-Za-z0-9_$]+)\s*\(")

    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        source_lines = content.splitlines()
        definitions: List[CodeNode] = []
        references: List[Tuple[CodeNode, Optional[str]]] = []
        current_class: Optional[CodeNode] = None
        current_func: Optional[CodeNode] = None

        for idx, line_str in enumerate(source_lines, start=1):
            clean = line_str.strip()
            if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*"):
                continue

            # 1. Class definition
            class_match = self.class_re.search(clean)
            if class_match:
                cname = class_match.group(1)
                if not is_builtin_or_stdlib(cname, "javascript"):
                    node_id = f"{file_path}:L{idx}:def:{cname}"
                    cnode = CodeNode(node_id, file_path, idx, cname, "def", "class", clean)
                    definitions.append(cnode)
                    current_class = cnode
                    current_func = None
                    continue

            # 2. Named function definition
            func_match = self.func_re.search(clean)
            if func_match and func_match.group(1):
                fname = func_match.group(1)
                if not is_builtin_or_stdlib(fname, "javascript"):
                    node_id = f"{file_path}:L{idx}:def:{fname}"
                    fnode = CodeNode(node_id, file_path, idx, fname, "def", "function", clean)
                    definitions.append(fnode)
                    current_func = fnode
                    continue

            # 3. Arrow function / variable assigned function
            arrow_match = self.arrow_or_assigned_func_re.search(clean)
            if arrow_match:
                fname = arrow_match.group(1)
                if not is_builtin_or_stdlib(fname, "javascript"):
                    node_id = f"{file_path}:L{idx}:def:{fname}"
                    fnode = CodeNode(node_id, file_path, idx, fname, "def", "function", clean)
                    definitions.append(fnode)
                    current_func = fnode
                    continue

            # 4. Class method
            if current_class:
                method_match = self.method_re.search(clean)
                if method_match:
                    mname = method_match.group(1)
                    if not is_builtin_or_stdlib(mname, "javascript") and mname not in ("constructor", "if", "for", "while", "switch"):
                        full_name = f"{current_class.name}.{mname}"
                        node_id = f"{file_path}:L{idx}:def:{full_name}"
                        mnode = CodeNode(node_id, file_path, idx, full_name, "def", "method", clean)
                        definitions.append(mnode)
                        current_func = mnode

            # 5. Call sites
            for call_match in self.call_re.finditer(clean):
                called = call_match.group(1)
                if not is_builtin_or_stdlib(called, "javascript"):
                    enclosing = current_func or current_class
                    if not enclosing or enclosing.name.split(".")[-1] != called:
                        ref_id = f"{file_path}:L{idx}:ref:{called}"
                        ref_node = CodeNode(ref_id, file_path, idx, called, "ref", "call", clean)
                        references.append((ref_node, enclosing.node_id if enclosing else None))

        return definitions, references
