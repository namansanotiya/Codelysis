"""
Universal Generic Pattern Parser for any programming language.
Serves as fallback and general multi-language handler.
"""
import re
from typing import List, Tuple, Optional
from core.types import CodeNode
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


class GenericParser(BaseParser):
    def __init__(self):
        self.class_re = re.compile(
            r"^\s*(?:export\s+)?(?:public|private|protected\s+)?(?:class|interface|struct|type|module)\s+([A-Za-z0-9_]+)"
        )
        self.func_re = re.compile(
            r"^\s*(?:export\s+)?(?:async\s+)?(?:def\s+|fn\s+|func\s+|function\s+|sub\s+)?(?:public|private|protected|static\s+)*"
            r"(?:[A-Za-z0-9_*&<>\[\]]+\s+)*([A-Za-z0-9_]+)\s*\([^;{]*\)\s*(?:{|=>|:\s*[\w]+|do)?"
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

            # 1. Class / Type / Struct
            class_match = self.class_re.search(clean)
            if class_match:
                cname = class_match.group(1)
                if not is_builtin_or_stdlib(cname):
                    node_id = f"{file_path}:L{idx}:def:{cname}"
                    cnode = CodeNode(node_id, file_path, idx, cname, "def", "class", clean)
                    definitions.append(cnode)
                    current_container = cnode
                    continue

            # 2. Function / Method
            func_match = self.func_re.search(clean)
            if func_match:
                fname = func_match.group(1)
                if not is_builtin_or_stdlib(fname):
                    category = "method" if current_container and current_container.category == "class" else "function"
                    node_id = f"{file_path}:L{idx}:def:{fname}"
                    fnode = CodeNode(node_id, file_path, idx, fname, "def", category, clean)
                    definitions.append(fnode)
                    current_container = fnode

            # 3. Call sites
            for call_match in self.call_re.finditer(clean):
                called = call_match.group(1)
                if not is_builtin_or_stdlib(called):
                    enclosing = current_container
                    if not enclosing or enclosing.name != called:
                        ref_id = f"{file_path}:L{idx}:ref:{called}"
                        ref_node = CodeNode(ref_id, file_path, idx, called, "ref", "call", clean)
                        references.append((ref_node, enclosing.node_id if enclosing else None))

        return definitions, references
