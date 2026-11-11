"""
Python AST Parser using Python's native ast module.
Extracts classes, functions, methods, call sites, imports, and inheritance hierarchies
with precise source locations (start/end lines, columns), signatures, and docstrings.
"""
import ast
import os
from typing import List, Tuple, Optional, Dict, Any
from core.types import CodeNode, ImportBinding, Category, NodeType
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


def format_func_signature(node: ast.AST) -> str:
    """Extract and format full parameter signature and return type from function def."""
    try:
        args = node.args
        total_args = list(args.posonlyargs) + list(args.args)
        num_defaults = len(args.defaults)
        offset = len(total_args) - num_defaults

        def_map = {}
        for idx, d in enumerate(args.defaults):
            def_map[offset + idx] = ast.unparse(d)

        arg_strs = []
        for i, a in enumerate(args.posonlyargs):
            ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
            default = f" = {def_map[i]}" if i in def_map else ""
            arg_strs.append(f"{a.arg}{ann}{default}")
        if args.posonlyargs:
            arg_strs.append("/")

        posonly_count = len(args.posonlyargs)
        for i, a in enumerate(args.args):
            global_idx = posonly_count + i
            ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
            default = f" = {def_map[global_idx]}" if global_idx in def_map else ""
            arg_strs.append(f"{a.arg}{ann}{default}")

        if args.vararg:
            ann = f": {ast.unparse(args.vararg.annotation)}" if args.vararg.annotation else ""
            arg_strs.append(f"*{args.vararg.arg}{ann}")
        elif args.kwonlyargs:
            arg_strs.append("*")

        for idx, a in enumerate(args.kwonlyargs):
            ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
            default = ""
            if idx < len(args.kw_defaults) and args.kw_defaults[idx] is not None:
                default = f" = {ast.unparse(args.kw_defaults[idx])}"
            arg_strs.append(f"{a.arg}{ann}{default}")

        if args.kwarg:
            ann = f": {ast.unparse(args.kwarg.annotation)}" if args.kwarg.annotation else ""
            arg_strs.append(f"**{args.kwarg.arg}{ann}")

        ret_ann = f" -> {ast.unparse(node.returns)}" if getattr(node, "returns", None) else ""
        return f"({', '.join(arg_strs)}){ret_ann}"
    except Exception:
        return "()"


class PythonASTVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str, source_lines: List[str]):
        self.rel_path = rel_path
        self.source_lines = source_lines
        self.definitions: List[CodeNode] = []
        self.references: List[Tuple[CodeNode, Optional[str]]] = []
        self.imports: List[ImportBinding] = []
        self.class_bases: Dict[str, List[str]] = {}  # class_name -> [base_names]
        self.current_scope: List[Tuple[str, str]] = []  # [(category, full_name)]
        # Counter for disambiguating multiple calls to same function at same line
        self._call_counters: Dict[Tuple[str, int, str], int] = {}

        # Module qualified prefix e.g. "auth/service.py" -> "auth.service"
        # For package __init__.py files, the module is the package directory name
        clean_path = rel_path.replace("\\", "/")
        if clean_path.endswith("/__init__.py"):
            pkg_dir = os.path.dirname(clean_path)
            self.module_prefix = pkg_dir.replace("/", ".").strip(".")
        elif clean_path == "__init__.py":
            self.module_prefix = ""
        else:
            no_ext, _ = os.path.splitext(clean_path)
            self.module_prefix = no_ext.replace("/", ".").strip(".")

    def visit_Import(self, node: ast.Import):
        line = node.lineno
        for alias in node.names:
            binding = ImportBinding(
                module=alias.name,
                symbol="",
                alias=alias.asname or alias.name,
                is_from_import=False,
                line=line
            )
            self.imports.append(binding)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        line = node.lineno
        module_name = node.module or ""
        for alias in node.names:
            binding = ImportBinding(
                module=module_name,
                symbol=alias.name,
                alias=alias.asname or alias.name,
                is_from_import=True,
                line=line
            )
            self.imports.append(binding)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name
        line = node.lineno
        end_line = getattr(node, "end_lineno", line)
        start_col = getattr(node, "col_offset", 0)
        end_col = getattr(node, "end_col_offset", 0)

        # Track full nested scope name e.g. OuterClass.InnerClass
        parent_scope_name = self.current_scope[-1][1] if self.current_scope else ""
        full_name = f"{parent_scope_name}.{class_name}" if parent_scope_name else class_name
        qualified_name = f"{self.module_prefix}.{full_name}" if self.module_prefix else full_name

        node_id = f"{self.rel_path}:L{line}:def:{full_name}"
        snippet = BaseParser.get_snippet(self.source_lines, line)
        docstring = ast.get_docstring(node) or ""

        # Extract base classes
        bases: List[str] = []
        for b in node.bases:
            try:
                base_str = ast.unparse(b)
                bases.append(base_str)
            except Exception:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
        if bases:
            self.class_bases[node_id] = bases

        code_node = CodeNode(
            node_id=node_id,
            file=self.rel_path,
            line=line,
            name=full_name,
            type=NodeType.DEF.value,
            category=Category.CLASS.value,
            end_line=end_line,
            start_col=start_col,
            end_col=end_col,
            qualified_name=qualified_name,
            signature=f"({', '.join(bases)})" if bases else "()",
            docstring=docstring,
            parent_scope=parent_scope_name,
            snippet=snippet,
            metadata={"bases": bases}
        )
        self.definitions.append(code_node)
        self.current_scope.append(("class", full_name))
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_func(node)

    def _handle_func(self, node):
        func_name = node.name
        line = node.lineno
        end_line = getattr(node, "end_lineno", line)
        start_col = getattr(node, "col_offset", 0)
        end_col = getattr(node, "end_col_offset", 0)

        is_method = len(self.current_scope) > 0 and self.current_scope[-1][0] == "class"
        category = Category.METHOD.value if is_method else Category.FUNCTION.value

        parent_scope_name = self.current_scope[-1][1] if self.current_scope else ""
        full_name = f"{parent_scope_name}.{func_name}" if parent_scope_name else func_name
        qualified_name = f"{self.module_prefix}.{full_name}" if self.module_prefix else full_name

        node_id = f"{self.rel_path}:L{line}:def:{full_name}"
        snippet = BaseParser.get_snippet(self.source_lines, line)
        signature = format_func_signature(node)
        docstring = ast.get_docstring(node) or ""

        code_node = CodeNode(
            node_id=node_id,
            file=self.rel_path,
            line=line,
            name=full_name,
            type=NodeType.DEF.value,
            category=category,
            end_line=end_line,
            start_col=start_col,
            end_col=end_col,
            qualified_name=qualified_name,
            signature=signature,
            docstring=docstring,
            parent_scope=parent_scope_name,
            snippet=snippet,
            metadata={
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "is_method": is_method,
                "parent_scope": parent_scope_name
            }
        )
        self.definitions.append(code_node)
        self.current_scope.append((category, full_name))
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_Call(self, node: ast.Call):
        called_name = None
        receiver = None

        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_name = node.func.attr
            try:
                receiver = ast.unparse(node.func.value)
            except Exception:
                receiver = getattr(node.func.value, "id", None)

        if called_name and not is_builtin_or_stdlib(called_name, language="python"):
            line = node.lineno
            end_line = getattr(node, "end_lineno", line)
            start_col = getattr(node, "col_offset", 0)
            end_col = getattr(node, "end_col_offset", 0)

            # Disambiguate multiple calls to the same name on the same line
            # using (file, line, col_offset) — AST guarantees unique col per call node.
            # Occurrence counter handles the theoretical edge case of duplicate col_offsets.
            occ = self._call_counters.get((self.rel_path, line, called_name, start_col), 0)
            self._call_counters[(self.rel_path, line, called_name, start_col)] = occ + 1
            # Use line + col to form a stable, unique reference ID
            ref_id = f"{self.rel_path}:L{line}:C{start_col}:ref:{called_name}"
            if occ > 0:
                # Safety net: should never happen in a valid AST
                ref_id = f"{ref_id}:{occ}"
            snippet = BaseParser.get_snippet(self.source_lines, line)

            # Enclosing definition lookup
            enclosing_id = None
            parent_scope_name = ""
            if self.current_scope:
                parent_scope_name = self.current_scope[-1][1]
                for d in reversed(self.definitions):
                    if d.name == parent_scope_name:
                        enclosing_id = d.node_id
                        break

            # Capture arguments count and keyword names for signature-matching
            arg_count = len(node.args)
            kw_names = [k.arg for k in node.keywords if k.arg]

            ref_node = CodeNode(
                node_id=ref_id,
                file=self.rel_path,
                line=line,
                name=called_name,
                type=NodeType.REF.value,
                category=Category.CALL.value,
                end_line=end_line,
                start_col=start_col,
                end_col=end_col,
                qualified_name=f"{self.module_prefix}.{parent_scope_name}.{called_name}" if parent_scope_name and self.module_prefix else (f"{self.module_prefix}.{called_name}" if self.module_prefix else called_name),
                parent_scope=parent_scope_name,
                snippet=snippet,
                metadata={
                    "receiver": receiver,
                    "arg_count": arg_count,
                    "kw_names": kw_names,
                    "full_call": f"{receiver}.{called_name}" if receiver else called_name
                }
            )

            self.references.append((ref_node, enclosing_id))

        self.generic_visit(node)


class PythonParser(BaseParser):
    def __init__(self):
        self._last_imports: List[ImportBinding] = []
        self._last_bases: Dict[str, List[str]] = {}

    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        source_lines = content.splitlines()
        self._last_imports = []
        self._last_bases = {}

        try:
            tree = ast.parse(content, filename=file_path)
            visitor = PythonASTVisitor(file_path, source_lines)
            visitor.visit(tree)
            self._last_imports = visitor.imports
            self._last_bases = visitor.class_bases
            return visitor.definitions, visitor.references
        except Exception:
            # Fallback to generic line parser if syntax error occurs
            from parsers.languages.generic import GenericParser
            return GenericParser().parse(file_path, content)

    def get_imports(self) -> List[ImportBinding]:
        return self._last_imports

    def get_class_bases(self) -> Dict[str, List[str]]:
        return self._last_bases
