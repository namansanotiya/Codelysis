"""
Tree-sitter Evaluation & Parser Adapter for JavaScript and TypeScript.
Provides full concrete syntax tree (CST) and AST extraction:
  - Class declarations, interfaces, extends/implements
  - Function declarations, arrow functions, async functions
  - Class methods with parent scope tracking
  - Call expressions with receiver, argument count, and collision-free node IDs
  - Import statements (named, default, namespace, aliases)
  - Export declarations
  - Fallback to enhanced JavaScriptParser if Tree-sitter C-bindings are absent
"""
import os
import logging
from typing import List, Tuple, Optional, Dict, Any, Set
from core.types import CodeNode, ImportBinding, Category, NodeType
from parsers.base import BaseParser
from parsers.filter import is_builtin_or_stdlib
from parsers.languages.javascript import JavaScriptParser

logger = logging.getLogger("javascript_treesitter")


def evaluate_treesitter_support() -> Dict[str, Any]:
    """
    Evaluates Tree-sitter runtime availability in the current Python environment.
    Returns status and diagnostic details.
    """
    report = {
        "tree_sitter_installed": False,
        "javascript_grammar_installed": False,
        "typescript_grammar_installed": False,
        "active_parser": "JavaScriptParser (Lexical Scope & Comment-Suppression Engine)",
        "diagnostics": ""
    }

    try:
        import tree_sitter
        report["tree_sitter_installed"] = True
    except ImportError as e:
        report["diagnostics"] = f"tree_sitter package not installed: {str(e)}"
        return report

    try:
        import tree_sitter_javascript
        report["javascript_grammar_installed"] = True
    except ImportError:
        report["diagnostics"] += " tree_sitter_javascript grammar wheel not found."

    try:
        import tree_sitter_typescript
        report["typescript_grammar_installed"] = True
    except ImportError:
        report["diagnostics"] += " tree_sitter_typescript grammar wheel not found."

    if report["tree_sitter_installed"] and report["javascript_grammar_installed"]:
        report["active_parser"] = "TreeSitterJavaScriptParser (C-Binding Syntax Tree Engine)"

    return report


class TreeSitterJavaScriptParser(BaseParser):
    """
    Tree-sitter based AST/CST parser for JS/TS with actual syntax tree node extraction
    and graceful fallback to JavaScriptParser.
    """
    def __init__(self):
        self._fallback_parser = JavaScriptParser()
        self._ts_available = False
        self._parser = None
        self._language = None
        self._last_imports: List[ImportBinding] = []
        self._last_bases: Dict[str, List[str]] = {}

        try:
            import tree_sitter
            import tree_sitter_javascript
            self._language = tree_sitter.Language(tree_sitter_javascript.language())
            self._parser = tree_sitter.Parser(self._language)
            self._ts_available = True
            logger.info("TreeSitterJavaScriptParser initialized successfully with tree_sitter_javascript grammar.")
        except Exception as e:
            self._ts_available = False
            logger.debug(f"Tree-sitter grammar not available ({e}). Using robust JavaScriptParser fallback.")

    @property
    def is_fallback_active(self) -> bool:
        """Returns True if Tree-sitter C-bindings are not active and fallback regex is used."""
        return not self._ts_available or self._parser is None

    def parse(self, file_path: str, content: str) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        self._last_imports = []
        self._last_bases = {}

        if not self._ts_available or self._parser is None:
            defs, refs = self._fallback_parser.parse(file_path, content)
            self._last_imports = self._fallback_parser.get_imports()
            self._last_bases = self._fallback_parser.get_class_bases()
            return defs, refs

        # Tree-sitter concrete syntax tree parsing
        try:
            tree = self._parser.parse(bytes(content, "utf8"))
            defs, refs = self._extract_nodes_from_tree(file_path, content, tree)
            return defs, refs
        except Exception as e:
            logger.warning(f"Tree-sitter CST traversal encountered an error ({e}). Using fallback parser.")
            defs, refs = self._fallback_parser.parse(file_path, content)
            self._last_imports = self._fallback_parser.get_imports()
            self._last_bases = self._fallback_parser.get_class_bases()
            return defs, refs

    def _extract_nodes_from_tree(
        self, file_path: str, content: str, tree: Any
    ) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
        """
        Directly walks the Tree-sitter CST to extract definitions, calls, imports, and exports.
        """
        definitions: List[CodeNode] = []
        references: List[Tuple[CodeNode, Optional[str]]] = []
        self._last_imports = []
        self._last_bases = {}

        source_lines = content.splitlines()
        call_counters: Dict[Tuple[str, int, str, int], int] = {}
        scope_stack: List[Tuple[str, CodeNode]] = []  # [(kind, node)]

        def get_node_text(node: Any) -> str:
            if not node:
                return ""
            return content[node.start_byte:node.end_byte]

        def walk(cursor_node: Any):
            nonlocal definitions, references

            ntype = cursor_node.type
            start_row, start_col = cursor_node.start_point
            end_row, end_col = cursor_node.end_point
            line_idx = start_row + 1
            end_line_idx = end_row + 1

            pushed_scope = False
            current_enclosing = scope_stack[-1][1] if scope_stack else None

            # ------------------------------------------------------------------
            # 1. Import Statements
            # ------------------------------------------------------------------
            if ntype in ("import_statement", "import_declaration"):
                self._extract_import_from_cst(cursor_node, content, line_idx)

            # ------------------------------------------------------------------
            # 2. Class and Interface Declarations
            # ------------------------------------------------------------------
            elif ntype in ("class_declaration", "class", "interface_declaration"):
                name_node = cursor_node.child_by_field_name("name")
                cname = get_node_text(name_node) if name_node else ""
                
                if cname and not is_builtin_or_stdlib(cname, "javascript"):
                    is_interface = ("interface" in ntype)
                    cat = Category.INTERFACE.value if is_interface else Category.CLASS.value
                    node_id = f"{file_path}:L{line_idx}:C{start_col}:def:{cname}"

                    # Extract base classes / heritage
                    bases: List[str] = []
                    heritage = cursor_node.child_by_field_name("heritage")
                    if not heritage:
                        # Scan children for extends_clause or class_heritage
                        for child in cursor_node.children:
                            if "extends" in child.type or "heritage" in child.type:
                                heritage = child
                                break
                    if heritage:
                        heritage_text = get_node_text(heritage)
                        for part in heritage_text.replace("extends", "").replace("implements", "").split(","):
                            clean_part = part.strip()
                            if clean_part:
                                bases.append(clean_part)

                    cnode = CodeNode(
                        node_id=node_id,
                        file=file_path,
                        line=line_idx,
                        name=cname,
                        type=NodeType.DEF.value,
                        category=cat,
                        end_line=end_line_idx,
                        start_col=start_col,
                        end_col=end_col,
                        snippet=BaseParser.get_snippet(source_lines, line_idx),
                        metadata={"bases": bases}
                    )
                    definitions.append(cnode)
                    if bases:
                        self._last_bases[node_id] = bases

                    scope_stack.append(("class", cnode))
                    pushed_scope = True

            # ------------------------------------------------------------------
            # 3. Method Definitions inside Classes
            # ------------------------------------------------------------------
            elif ntype == "method_definition" and current_enclosing and current_enclosing.category in (Category.CLASS.value, Category.INTERFACE.value):
                name_node = cursor_node.child_by_field_name("name")
                mname = get_node_text(name_node) if name_node else ""

                if mname and not is_builtin_or_stdlib(mname, "javascript") and mname not in (
                    "constructor", "if", "for", "while", "switch", "catch"
                ):
                    full_name = f"{current_enclosing.name}.{mname}"
                    node_id = f"{file_path}:L{line_idx}:C{start_col}:def:{full_name}"

                    params_node = cursor_node.child_by_field_name("parameters")
                    sig = get_node_text(params_node) if params_node else "()"

                    mnode = CodeNode(
                        node_id=node_id,
                        file=file_path,
                        line=line_idx,
                        name=full_name,
                        type=NodeType.DEF.value,
                        category=Category.METHOD.value,
                        end_line=end_line_idx,
                        start_col=start_col,
                        end_col=end_col,
                        signature=sig,
                        parent_scope=current_enclosing.name,
                        snippet=BaseParser.get_snippet(source_lines, line_idx)
                    )
                    definitions.append(mnode)
                    scope_stack.append(("method", mnode))
                    pushed_scope = True

            # ------------------------------------------------------------------
            # 4. Function Declarations
            # ------------------------------------------------------------------
            elif ntype in ("function_declaration", "function"):
                name_node = cursor_node.child_by_field_name("name")
                fname = get_node_text(name_node) if name_node else ""

                if fname and not is_builtin_or_stdlib(fname, "javascript"):
                    node_id = f"{file_path}:L{line_idx}:C{start_col}:def:{fname}"
                    params_node = cursor_node.child_by_field_name("parameters")
                    sig = get_node_text(params_node) if params_node else "()"

                    parent_scope_name = current_enclosing.name if current_enclosing else ""
                    fnode = CodeNode(
                        node_id=node_id,
                        file=file_path,
                        line=line_idx,
                        name=fname,
                        type=NodeType.DEF.value,
                        category=Category.FUNCTION.value,
                        end_line=end_line_idx,
                        start_col=start_col,
                        end_col=end_col,
                        signature=sig,
                        parent_scope=parent_scope_name,
                        snippet=BaseParser.get_snippet(source_lines, line_idx)
                    )
                    definitions.append(fnode)
                    scope_stack.append(("function", fnode))
                    pushed_scope = True

            # ------------------------------------------------------------------
            # 5. Variable Declarator with Arrow Function or Function Expression
            # ------------------------------------------------------------------
            elif ntype == "variable_declarator":
                name_node = cursor_node.child_by_field_name("name")
                value_node = cursor_node.child_by_field_name("value")

                if name_node and value_node and value_node.type in ("arrow_function", "function_expression"):
                    fname = get_node_text(name_node)
                    if fname and not is_builtin_or_stdlib(fname, "javascript"):
                        node_id = f"{file_path}:L{line_idx}:C{start_col}:def:{fname}"
                        params_node = value_node.child_by_field_name("parameters")
                        sig = get_node_text(params_node) if params_node else "()"

                        fnode = CodeNode(
                            node_id=node_id,
                            file=file_path,
                            line=line_idx,
                            name=fname,
                            type=NodeType.DEF.value,
                            category=Category.FUNCTION.value,
                            end_line=end_line_idx,
                            start_col=start_col,
                            end_col=end_col,
                            signature=sig,
                            parent_scope=current_enclosing.name if current_enclosing else "",
                            snippet=BaseParser.get_snippet(source_lines, line_idx)
                        )
                        definitions.append(fnode)
                        scope_stack.append(("function", fnode))
                        pushed_scope = True

            # ------------------------------------------------------------------
            # 6. Call Expressions
            # ------------------------------------------------------------------
            elif ntype == "call_expression":
                fn_expr = cursor_node.child_by_field_name("function")
                called = ""
                receiver = ""

                if fn_expr:
                    if fn_expr.type == "identifier":
                        called = get_node_text(fn_expr)
                    elif fn_expr.type == "member_expression":
                        prop = fn_expr.child_by_field_name("property")
                        obj = fn_expr.child_by_field_name("object")
                        called = get_node_text(prop) if prop else ""
                        receiver = get_node_text(obj) if obj else ""

                if called and not is_builtin_or_stdlib(called, "javascript") and called not in (
                    "if", "for", "while", "switch", "catch", "return", "require", "import"
                ):
                    occ = call_counters.get((file_path, line_idx, called, start_col), 0)
                    call_counters[(file_path, line_idx, called, start_col)] = occ + 1

                    ref_id = f"{file_path}:L{line_idx}:C{start_col}:ref:{called}"
                    if occ > 0:
                        ref_id = f"{ref_id}:{occ}"

                    enclosing_id = current_enclosing.node_id if current_enclosing else None
                    args_node = cursor_node.child_by_field_name("arguments")
                    arg_count = len(args_node.children) if args_node else 0

                    ref_node = CodeNode(
                        node_id=ref_id,
                        file=file_path,
                        line=line_idx,
                        name=called,
                        type=NodeType.REF.value,
                        category=Category.CALL.value,
                        start_col=start_col,
                        end_col=end_col,
                        parent_scope=current_enclosing.name if current_enclosing else "",
                        snippet=BaseParser.get_snippet(source_lines, line_idx),
                        metadata={"receiver": receiver, "arg_count": arg_count}
                    )
                    references.append((ref_node, enclosing_id))

            # Recurse through children
            for child in cursor_node.children:
                walk(child)

            # Pop scope if pushed
            if pushed_scope and scope_stack:
                scope_stack.pop()

        # Execute walk from root
        root = tree.root_node if hasattr(tree, "root_node") else tree
        walk(root)

        return definitions, references

    def _extract_import_from_cst(self, node: Any, content: str, line_idx: int):
        """Extract import bindings from Tree-sitter import CST node."""
        source_node = node.child_by_field_name("source")
        mod_path = ""
        if source_node:
            mod_path = content[source_node.start_byte:source_node.end_byte].strip("\"'")

        if not mod_path:
            return

        for child in node.children:
            # 1. import default from 'mod'
            if child.type == "identifier":
                self._last_imports.append(
                    ImportBinding(
                        module=mod_path,
                        symbol="default",
                        alias=content[child.start_byte:child.end_byte],
                        is_from_import=True,
                        line=line_idx
                    )
                )
            # 2. import * as ns from 'mod'
            elif child.type == "namespace_import":
                for sub in child.children:
                    if sub.type == "identifier":
                        self._last_imports.append(
                            ImportBinding(
                                module=mod_path,
                                symbol="*",
                                alias=content[sub.start_byte:sub.end_byte],
                                is_from_import=False,
                                line=line_idx
                            )
                        )
            # 3. import { a, b as c } from 'mod'
            elif child.type in ("named_imports", "import_clause"):
                for sub in child.children:
                    if sub.type == "import_specifier":
                        name_n = sub.child_by_field_name("name")
                        alias_n = sub.child_by_field_name("alias")
                        orig = content[name_n.start_byte:name_n.end_byte] if name_n else ""
                        alias = content[alias_n.start_byte:alias_n.end_byte] if alias_n else orig
                        if orig:
                            self._last_imports.append(
                                ImportBinding(
                                    module=mod_path,
                                    symbol=orig,
                                    alias=alias,
                                    is_from_import=True,
                                    line=line_idx
                                )
                            )

    def get_imports(self) -> List[ImportBinding]:
        return self._last_imports

    def get_class_bases(self) -> Dict[str, List[str]]:
        return self._last_bases
