"""
JavaScript and TypeScript Parser (ES6+, TypeScript, JSX, TSX).
Extracts classes, interfaces, functions, arrow functions, methods, call sites,
imports, exports, and inheritance with precise line/col spans and comment suppression.
"""
import re
from typing import List, Tuple, Optional, Dict, Set
from core.types import CodeNode, ImportBinding, Category, NodeType
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


def strip_js_comments_and_strings(content: str) -> List[Tuple[int, str, str]]:
    """
    Strips single-line and multi-line comments and string literal contents
    while preserving original line numbers and character positions for column indexing.
    Returns list of (line_number, original_line, sanitized_line).
    """
    lines = content.splitlines()
    sanitized_lines = []
    in_block_comment = False

    for line_idx, line in enumerate(lines, start=1):
        sanitized = []
        i = 0
        n = len(line)
        in_string: Optional[str] = None  # '"', "'", '`'

        while i < n:
            # Inside block comment
            if in_block_comment:
                if i + 1 < n and line[i:i+2] == "*/":
                    in_block_comment = False
                    sanitized.append("  ")
                    i += 2
                else:
                    sanitized.append(" ")
                    i += 1
                continue

            # Inside string literal
            if in_string:
                if line[i] == "\\":
                    sanitized.append("  ")
                    i += 2
                    continue
                elif line[i] == in_string:
                    in_string = None
                    sanitized.append(" ")
                    i += 1
                    continue
                else:
                    sanitized.append(" ")
                    i += 1
                    continue

            # Start of comments or strings
            if i + 1 < n and line[i:i+2] == "//":
                # Single-line comment: blank out remainder of line
                sanitized.append(" " * (n - i))
                break
            elif i + 1 < n and line[i:i+2] == "/*":
                in_block_comment = True
                sanitized.append("  ")
                i += 2
                continue
            elif line[i] in ('"', "'", '`'):
                in_string = line[i]
                sanitized.append(" ")
                i += 1
                continue
            else:
                sanitized.append(line[i])
                i += 1

        sanitized_lines.append((line_idx, line, "".join(sanitized)))

    return sanitized_lines


class JavaScriptParser(BaseParser):
    def __init__(self):
        self._last_imports: List[ImportBinding] = []
        self._last_bases: Dict[str, List[str]] = {}

        # Regex patterns against sanitized code
        self.class_re = re.compile(
            r"(?:export\s+(?:default\s+)?)?(?:class|interface)\s+([A-Za-z0-9_$]+)(?:\s+(?:extends|implements)\s+([A-Za-z0-9_$,\s.]+))?"
        )
        self.func_re = re.compile(
            r"(?:export\s+(?:default\s+)?)?(?:async\s+)?function(?:\s+([A-Za-z0-9_$]+))?\s*\("
        )
        self.arrow_func_re = re.compile(
            r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>"
        )
        self.assigned_func_re = re.compile(
            r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?function\s*\("
        )
        self.method_re = re.compile(
            r"^\s*(?:(?:public|private|protected|static|async|override)\s+)*([A-Za-z0-9_$]+)\s*\([^)]*\)\s*(?::\s*[\w<>\[\]\s|&]+\s*)?\{"
        )
        self.call_re = re.compile(r"(?:(\b[A-Za-z0-9_$]+)\.)?\b([A-Za-z0-9_$]+)\s*\(")
        
        # Imports: handles combined, named, default, alias, and namespace imports
        self.import_combined_re = re.compile(r"import\s+([A-Za-z0-9_$]+)\s*,\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]")
        self.import_named_re = re.compile(r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]")
        self.import_default_re = re.compile(r"import\s+([A-Za-z0-9_$]+)\s+from\s*['\"]([^'\"]+)['\"]")
        self.import_namespace_re = re.compile(r"import\s*\*\s*as\s+([A-Za-z0-9_$]+)\s+from\s*['\"]([^'\"]+)['\"]")
        self.require_re = re.compile(r"(?:const|let|var)\s+(?:\{([^}]+)\}|([A-Za-z0-9_$]+))\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")

    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        sanitized_info = strip_js_comments_and_strings(content)
        definitions: List[CodeNode] = []
        references: List[Tuple[CodeNode, Optional[str]]] = []
        self._last_imports = []
        self._last_bases = {}

        call_counters: Dict[Tuple[str, int, str], int] = {}
        scope_stack: List[Tuple[str, CodeNode, int]] = []  # [(kind, node, brace_depth)]
        current_brace_depth = 0

        source_lines = [orig for _, orig, _ in sanitized_info]

        for line_idx, orig_line, clean_line in sanitized_info:
            trimmed = clean_line.strip()
            
            # Update brace depth and pop scope if exited
            open_braces = clean_line.count("{")
            close_braces = clean_line.count("}")
            
            # Pre-check imports on original line (since imports can have string paths)
            self._parse_imports(orig_line, line_idx)

            if not trimmed:
                current_brace_depth += (open_braces - close_braces)
                self._maintain_scope(scope_stack, current_brace_depth)
                continue

            current_enclosing = scope_stack[-1][1] if scope_stack else None

            # 1. Class or Interface definition
            class_match = self.class_re.search(clean_line)
            if class_match:
                cname = class_match.group(1)
                super_clause = class_match.group(2)
                is_interface = "interface" in clean_line[:class_match.start(1)]
                cat = Category.INTERFACE.value if is_interface else Category.CLASS.value

                if not is_builtin_or_stdlib(cname, "javascript"):
                    col_offset = class_match.start(1)
                    node_id = f"{file_path}:L{line_idx}:C{col_offset}:def:{cname}"
                    bases = [b.strip() for b in super_clause.split(",")] if super_clause else []
                    cnode = CodeNode(
                        node_id=node_id,
                        file=file_path,
                        line=line_idx,
                        name=cname,
                        type=NodeType.DEF.value,
                        category=cat,
                        start_col=col_offset,
                        end_col=col_offset + len(cname),
                        snippet=BaseParser.get_snippet(source_lines, line_idx),
                        metadata={"bases": bases}
                    )
                    definitions.append(cnode)
                    if bases:
                        self._last_bases[node_id] = bases
                    
                    scope_stack.append(("class", cnode, current_brace_depth + open_braces))
                    current_brace_depth += (open_braces - close_braces)
                    continue

            # 2. Function declaration
            func_match = self.func_re.search(clean_line)
            if func_match and func_match.group(1):
                fname = func_match.group(1)
                if not is_builtin_or_stdlib(fname, "javascript"):
                    col_offset = func_match.start(1)
                    node_id = f"{file_path}:L{line_idx}:C{col_offset}:def:{fname}"
                    fnode = CodeNode(
                        node_id=node_id,
                        file=file_path,
                        line=line_idx,
                        name=fname,
                        type=NodeType.DEF.value,
                        category=Category.FUNCTION.value,
                        start_col=col_offset,
                        end_col=col_offset + len(fname),
                        snippet=BaseParser.get_snippet(source_lines, line_idx)
                    )
                    definitions.append(fnode)
                    scope_stack.append(("function", fnode, current_brace_depth + open_braces))
                    current_brace_depth += (open_braces - close_braces)
                    continue

            # 3. Arrow function or assigned function
            arrow_match = self.arrow_func_re.search(clean_line) or self.assigned_func_re.search(clean_line)
            if arrow_match and arrow_match.group(1):
                fname = arrow_match.group(1)
                if not is_builtin_or_stdlib(fname, "javascript"):
                    col_offset = arrow_match.start(1)
                    node_id = f"{file_path}:L{line_idx}:C{col_offset}:def:{fname}"
                    fnode = CodeNode(
                        node_id=node_id,
                        file=file_path,
                        line=line_idx,
                        name=fname,
                        type=NodeType.DEF.value,
                        category=Category.FUNCTION.value,
                        start_col=col_offset,
                        end_col=col_offset + len(fname),
                        snippet=BaseParser.get_snippet(source_lines, line_idx)
                    )
                    definitions.append(fnode)
                    scope_stack.append(("function", fnode, current_brace_depth + open_braces))
                    current_brace_depth += (open_braces - close_braces)
                    continue

            # 4. Class method
            if current_enclosing and current_enclosing.category in (Category.CLASS.value, Category.INTERFACE.value):
                method_match = self.method_re.search(clean_line)
                if method_match:
                    mname = method_match.group(1)
                    if not is_builtin_or_stdlib(mname, "javascript") and mname not in (
                        "constructor", "if", "for", "while", "switch", "catch"
                    ):
                        col_offset = method_match.start(1)
                        full_name = f"{current_enclosing.name}.{mname}"
                        node_id = f"{file_path}:L{line_idx}:C{col_offset}:def:{full_name}"
                        mnode = CodeNode(
                            node_id=node_id,
                            file=file_path,
                            line=line_idx,
                            name=full_name,
                            type=NodeType.DEF.value,
                            category=Category.METHOD.value,
                            start_col=col_offset,
                            end_col=col_offset + len(mname),
                            parent_scope=current_enclosing.name,
                            snippet=BaseParser.get_snippet(source_lines, line_idx)
                        )
                        definitions.append(mnode)
                        scope_stack.append(("method", mnode, current_brace_depth + open_braces))
                        current_brace_depth += (open_braces - close_braces)
                        continue

            # 5. Call sites
            for call_match in self.call_re.finditer(clean_line):
                receiver = call_match.group(1)
                called = call_match.group(2)
                
                # Filter keywords and language constructs
                if called in ("if", "for", "while", "switch", "catch", "return", "function", "import", "require"):
                    continue
                if is_builtin_or_stdlib(called, "javascript"):
                    continue

                col_offset = call_match.start(2)
                # Collision disambiguation for multiple calls on same line
                occ = call_counters.get((file_path, line_idx, called), 0)
                call_counters[(file_path, line_idx, called)] = occ + 1
                
                ref_id = f"{file_path}:L{line_idx}:C{col_offset}:ref:{called}"
                if occ > 0:
                    ref_id = f"{ref_id}:{occ}"

                enclosing_id = current_enclosing.node_id if current_enclosing else None
                ref_node = CodeNode(
                    node_id=ref_id,
                    file=file_path,
                    line=line_idx,
                    name=called,
                    type=NodeType.REF.value,
                    category=Category.CALL.value,
                    start_col=col_offset,
                    end_col=col_offset + len(called),
                    parent_scope=current_enclosing.name if current_enclosing else "",
                    snippet=BaseParser.get_snippet(source_lines, line_idx),
                    metadata={"receiver": receiver}
                )
                references.append((ref_node, enclosing_id))

            current_brace_depth += (open_braces - close_braces)
            self._maintain_scope(scope_stack, current_brace_depth)

        return definitions, references

    def _maintain_scope(self, scope_stack: List[Tuple[str, CodeNode, int]], current_depth: int):
        """Pop scopes that have closed."""
        while scope_stack and current_depth < scope_stack[-1][2]:
            scope_stack.pop()

    def _parse_imports(self, orig_line: str, line_idx: int):
        """Parse ES6 and CommonJS import statements."""
        # 0. import defaultExport, { named } from 'module'
        comb_match = self.import_combined_re.search(orig_line)
        if comb_match:
            default_name, symbols_str, mod_path = comb_match.groups()
            self._last_imports.append(ImportBinding(
                module=mod_path,
                symbol="default",
                alias=default_name,
                is_from_import=True,
                line=line_idx
            ))
            for s in symbols_str.split(","):
                s = s.strip()
                if not s:
                    continue
                if " as " in s:
                    orig, alias = s.split(" as ")
                    orig, alias = orig.strip(), alias.strip()
                else:
                    orig, alias = s, s
                self._last_imports.append(ImportBinding(
                    module=mod_path,
                    symbol=orig,
                    alias=alias,
                    is_from_import=True,
                    line=line_idx
                ))
            return

        # 1. import { a, b as c } from 'module'
        named_match = self.import_named_re.search(orig_line)
        if named_match:
            symbols_str, mod_path = named_match.groups()
            for s in symbols_str.split(","):
                s = s.strip()
                if not s:
                    continue
                if " as " in s:
                    orig, alias = s.split(" as ")
                    orig, alias = orig.strip(), alias.strip()
                else:
                    orig, alias = s, s
                self._last_imports.append(ImportBinding(
                    module=mod_path,
                    symbol=orig,
                    alias=alias,
                    is_from_import=True,
                    line=line_idx
                ))
            return

        # 2. import defaultExport from 'module'
        default_match = self.import_default_re.search(orig_line)
        if default_match:
            default_name, mod_path = default_match.groups()
            self._last_imports.append(ImportBinding(
                module=mod_path,
                symbol="default",
                alias=default_name,
                is_from_import=True,
                line=line_idx
            ))
            return

        # 3. import * as ns from 'module'
        ns_match = self.import_namespace_re.search(orig_line)
        if ns_match:
            ns_name, mod_path = ns_match.groups()
            self._last_imports.append(ImportBinding(
                module=mod_path,
                symbol="*",
                alias=ns_name,
                is_from_import=False,
                line=line_idx
            ))
            return

        # 4. const x = require('module') or const { x } = require('module')
        req_match = self.require_re.search(orig_line)
        if req_match:
            destruct, direct, mod_path = req_match.groups()
            if direct:
                self._last_imports.append(ImportBinding(
                    module=mod_path,
                    symbol="",
                    alias=direct,
                    is_from_import=False,
                    line=line_idx
                ))
            elif destruct:
                for s in destruct.split(","):
                    s = s.strip()
                    if not s:
                        continue
                    if ":" in s:
                        orig, alias = s.split(":")
                        orig, alias = orig.strip(), alias.strip()
                    else:
                        orig, alias = s, s
                    self._last_imports.append(ImportBinding(
                        module=mod_path,
                        symbol=orig,
                        alias=alias,
                        is_from_import=True,
                        line=line_idx
                    ))

    def get_imports(self) -> List[ImportBinding]:
        return self._last_imports

    def get_class_bases(self) -> Dict[str, List[str]]:
        return self._last_bases
