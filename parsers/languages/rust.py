"""
Rust Source Parser.
Extracts structs, enums, impl blocks, functions, and call invocations.
"""
import re
from typing import List, Tuple, Optional
from core.types import CodeNode
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


class RustParser(BaseParser):
    def __init__(self):
        self.type_re = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait)\s+([A-Za-z0-9_]+)")
        self.impl_re = re.compile(r"^\s*impl(?:\s*<[^>]+>)?\s+(?:[A-Za-z0-9_]+\s+for\s+)?([A-Za-z0-9_]+)")
        self.func_re = re.compile(
            r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+([A-Za-z0-9_]+)\s*\("
        )
        self.call_re = re.compile(r"\b([A-Za-z0-9_]+)\s*\(")

    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        source_lines = content.splitlines()
        definitions: List[CodeNode] = []
        references: List[Tuple[CodeNode, Optional[str]]] = []
        current_impl: Optional[str] = None
        current_def: Optional[CodeNode] = None

        brace_depth = 0
        impl_depth = None

        for idx, line_str in enumerate(source_lines, start=1):
            clean = line_str.strip()
            if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*"):
                continue

            # Check for closing impl block
            if clean == "}" and brace_depth <= 1:
                current_impl = None
                current_def = None

            # 1. Struct / Enum / Trait
            type_match = self.type_re.search(clean)
            if type_match:
                tname = type_match.group(1)
                if not is_builtin_or_stdlib(tname, "rust"):
                    node_id = f"{file_path}:L{idx}:def:{tname}"
                    tnode = CodeNode(node_id, file_path, idx, tname, "def", "struct", clean)
                    definitions.append(tnode)
                    current_def = tnode

            # 2. Impl block tracking
            impl_match = self.impl_re.search(clean)
            if impl_match:
                current_impl = impl_match.group(1)
                impl_depth = brace_depth

            # 3. Function / Method
            func_match = self.func_re.search(clean)
            if func_match:
                fname = func_match.group(1)
                if not is_builtin_or_stdlib(fname, "rust"):
                    category = "method" if current_impl else "function"
                    full_name = f"{current_impl}::{fname}" if current_impl else fname
                    node_id = f"{file_path}:L{idx}:def:{full_name}"
                    fnode = CodeNode(node_id, file_path, idx, full_name, "def", category, clean)
                    definitions.append(fnode)
                    current_def = fnode

            opens = clean.count("{")
            closes = clean.count("}")
            brace_depth += (opens - closes)
            if brace_depth <= 0:
                brace_depth = 0
                current_impl = None
                current_def = None

            # 4. Call sites
            for call_match in self.call_re.finditer(clean):
                called = call_match.group(1)
                if not is_builtin_or_stdlib(called, "rust"):
                    enclosing = current_def
                    if not enclosing or enclosing.name.split("::")[-1] != called:
                        ref_id = f"{file_path}:L{idx}:ref:{called}"
                        ref_node = CodeNode(ref_id, file_path, idx, called, "ref", "call", clean)
                        references.append((ref_node, enclosing.node_id if enclosing else None))

        return definitions, references
