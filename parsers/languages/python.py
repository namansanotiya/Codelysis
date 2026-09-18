"""
Python AST Parser using Python's native ast module.
Extracts classes, functions, methods, and call sites.
"""
import ast
from typing import List, Tuple, Optional
from core.types import CodeNode
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib


class PythonASTVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str, source_lines: List[str]):
        self.rel_path = rel_path
        self.source_lines = source_lines
        self.definitions: List[CodeNode] = []
        self.references: List[Tuple[CodeNode, Optional[str]]] = []
        self.current_scope: List[Tuple[str, str]] = []  # [(category, full_name)]

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name
        line = node.lineno
        node_id = f"{self.rel_path}:L{line}:def:{class_name}"
        snippet = BaseParser.get_snippet(self.source_lines, line)

        code_node = CodeNode(
            node_id=node_id,
            file=self.rel_path,
            line=line,
            name=class_name,
            type="def",
            category="class",
            snippet=snippet
        )
        self.definitions.append(code_node)
        self.current_scope.append(("class", class_name))
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_func(node)

    def _handle_func(self, node):
        func_name = node.name
        line = node.lineno
        is_method = len(self.current_scope) > 0 and self.current_scope[-1][0] == "class"
        category = "method" if is_method else "function"

        full_name = f"{self.current_scope[-1][1]}.{func_name}" if is_method else func_name
        node_id = f"{self.rel_path}:L{line}:def:{full_name}"
        snippet = BaseParser.get_snippet(self.source_lines, line)

        code_node = CodeNode(
            node_id=node_id,
            file=self.rel_path,
            line=line,
            name=full_name,
            type="def",
            category=category,
            snippet=snippet
        )
        self.definitions.append(code_node)
        self.current_scope.append((category, full_name))
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_Call(self, node: ast.Call):
        called_name = None
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_name = node.func.attr

        if called_name and not is_builtin_or_stdlib(called_name, language="python"):
            line = node.lineno
            ref_id = f"{self.rel_path}:L{line}:ref:{called_name}"
            snippet = BaseParser.get_snippet(self.source_lines, line)

            ref_node = CodeNode(
                node_id=ref_id,
                file=self.rel_path,
                line=line,
                name=called_name,
                type="ref",
                category="call",
                snippet=snippet
            )

            enclosing_id = None
            if self.current_scope:
                enclosing_name = self.current_scope[-1][1]
                for d in reversed(self.definitions):
                    if d.name == enclosing_name:
                        enclosing_id = d.node_id
                        break

            self.references.append((ref_node, enclosing_id))

        self.generic_visit(node)


class PythonParser(BaseParser):
    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        source_lines = content.splitlines()
        try:
            tree = ast.parse(content, filename=file_path)
            visitor = PythonASTVisitor(file_path, source_lines)
            visitor.visit(tree)
            return visitor.definitions, visitor.references
        except Exception:
            # Fallback to generic line parser if syntax error occurs
            from parsers.languages.generic import GenericParser
            return GenericParser().parse(file_path, content)
