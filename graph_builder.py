"""
Multi-Language Repository Graph Builder.
Constructs line & symbol directed code dependency graph G = (V, E) for Python, JS/TS, Java, C/C++, and Go.
"""
import ast
import os
import re
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Set, Optional, Tuple, Any
import networkx as nx

from code_impact_graph_rag.config import SUPPORTED_EXTENSIONS, STDLIB_MODULES

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("graph_builder")

BUILTIN_KEYWORDS: Set[str] = STDLIB_MODULES | {
    "if", "else", "elif", "for", "while", "do", "switch", "case", "default",
    "try", "catch", "finally", "throw", "throws", "return", "new", "delete",
    "sizeof", "typeof", "instanceof", "class", "interface", "struct", "import",
    "export", "package", "using", "namespace", "public", "private", "protected",
    "static", "final", "const", "let", "var", "function", "func", "async", "await",
    "make", "append", "len", "cap", "print", "println", "Printf", "Println"
}


@dataclass
class CodeNode:
    node_id: str
    file: str
    line: int
    name: str
    type: str        # 'def' (definition) or 'ref' (reference/invocation)
    category: str    # 'file', 'class', 'function', 'method', 'call'
    snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def get_snippet(lines: List[str], line_no: int) -> str:
    """Return stripped line snippet (1-indexed line_no)."""
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()
    return ""


# ==========================================
# 1. Python AST Parser
# ==========================================

class PythonASTVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str, source_lines: List[str]):
        self.rel_path = rel_path
        self.source_lines = source_lines
        self.definitions: List[CodeNode] = []
        self.references: List[Tuple[CodeNode, Optional[str]]] = []
        self.current_scope: List[Tuple[str, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name
        line = node.lineno
        node_id = f"{self.rel_path}:L{line}:def:{class_name}"
        snippet = get_snippet(self.source_lines, line)

        code_node = CodeNode(node_id=node_id, file=self.rel_path, line=line, name=class_name, type="def", category="class", snippet=snippet)
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
        snippet = get_snippet(self.source_lines, line)

        code_node = CodeNode(node_id=node_id, file=self.rel_path, line=line, name=full_name, type="def", category=category, snippet=snippet)
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

        if called_name and called_name not in BUILTIN_KEYWORDS:
            line = node.lineno
            ref_node_id = f"{self.rel_path}:L{line}:ref:{called_name}"
            snippet = get_snippet(self.source_lines, line)

            ref_node = CodeNode(node_id=ref_node_id, file=self.rel_path, line=line, name=called_name, type="ref", category="call", snippet=snippet)
            
            enclosing_id = None
            if self.current_scope:
                enclosing_name = self.current_scope[-1][1]
                for d in reversed(self.definitions):
                    if d.name == enclosing_name:
                        enclosing_id = d.node_id
                        break

            self.references.append((ref_node, enclosing_id))
        self.generic_visit(node)


# ==========================================
# 2. Multi-Language Pattern Parser (JS/TS, Java, C/C++, Go)
# ==========================================

def parse_generic_source(rel_path: str, source_lines: List[str]) -> Tuple[List[CodeNode], List[Tuple[CodeNode, Optional[str]]]]:
    """
    Parse definitions and references for JS/TS, Java, C/C++, and Go using multi-language patterns.
    """
    definitions: List[CodeNode] = []
    references: List[Tuple[CodeNode, Optional[str]]] = []
    current_enclosing_def: Optional[CodeNode] = None

    # Regex Patterns
    class_re = re.compile(r"^\s*(?:export\s+)?(?:public|private|protected\s+)?(?:class|interface|struct|type)\s+([A-Za-z0-9_]+)")
    func_re = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?(?:public|private|protected|static|func\s+)?(?:[A-Za-z0-9_*&<>\[\]]+\s+)*"
        r"([A-Za-z0-9_]+)\s*\([^;{]*\)\s*(?:{|=>|:\s*[\w]+)"
    )
    call_re = re.compile(r"\b([A-Za-z0-9_]+)\s*\(")

    for idx, line_str in enumerate(source_lines, start=1):
        clean_line = line_str.strip()
        if not clean_line or clean_line.startswith("//") or clean_line.startswith("/*") or clean_line.startswith("*"):
            continue

        # 1. Class / Type Definitions
        class_match = class_re.search(clean_line)
        if class_match:
            cname = class_match.group(1)
            if cname not in BUILTIN_KEYWORDS:
                node_id = f"{rel_path}:L{idx}:def:{cname}"
                cnode = CodeNode(node_id=node_id, file=rel_path, line=idx, name=cname, type="def", category="class", snippet=clean_line)
                definitions.append(cnode)
                current_enclosing_def = cnode
                continue

        # 2. Function / Method Definitions
        func_match = func_re.search(clean_line)
        if func_match:
            fname = func_match.group(1)
            if fname not in BUILTIN_KEYWORDS:
                category = "method" if current_enclosing_def and current_enclosing_def.category == "class" else "function"
                node_id = f"{rel_path}:L{idx}:def:{fname}"
                fnode = CodeNode(node_id=node_id, file=rel_path, line=idx, name=fname, type="def", category=category, snippet=clean_line)
                definitions.append(fnode)
                current_enclosing_def = fnode

        # 3. Call sites / References
        for call_match in call_re.finditer(clean_line):
            called_symbol = call_match.group(1)
            if called_symbol not in BUILTIN_KEYWORDS and (not current_enclosing_def or current_enclosing_def.name != called_symbol):
                ref_id = f"{rel_path}:L{idx}:ref:{called_symbol}"
                ref_node = CodeNode(node_id=ref_id, file=rel_path, line=idx, name=called_symbol, type="ref", category="call", snippet=clean_line)
                enclosing_id = current_enclosing_def.node_id if current_enclosing_def else None
                references.append((ref_node, enclosing_id))

    return definitions, references


# ==========================================
# 3. Main Repository Graph Builder
# ==========================================

def scan_repo_files(repo_path: str) -> List[str]:
    """Find all supported source files in target repository."""
    supported_files = []
    repo_path = os.path.abspath(repo_path)
    for root, _, files in os.walk(repo_path):
        for file in files:
            if any(file.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path).replace("\\", "/")
                supported_files.append(rel_path)
    return sorted(supported_files)


def build_graph(repo_path: str) -> nx.DiGraph:
    """
    Build directed repository dependency graph G = (V, E) supporting multi-language repos.
    """
    graph = nx.DiGraph()
    repo_path = os.path.abspath(repo_path)
    logger.info(f"Scanning repository: {repo_path}")

    files = scan_repo_files(repo_path)
    logger.info(f"Found {len(files)} multi-language source files ({', '.join(set(os.path.splitext(f)[1] for f in files))})")

    symbol_defs: Dict[str, List[CodeNode]] = {}
    file_nodes: Dict[str, CodeNode] = {}
    all_references: List[Tuple[str, CodeNode, Optional[str]]] = []  # (file_rel_path, ref_node, enclosing_def_id)

    # Pass 1: Parse definitions across Python & Multi-Language files
    for rel_path in files:
        full_path = os.path.join(repo_path, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            source_lines = content.splitlines()
        except Exception as e:
            logger.warning(f"Reading file failed for {rel_path}: {e}")
            continue

        # File Node
        file_node_id = f"{rel_path}:L1:def:{os.path.basename(rel_path)}"
        file_node = CodeNode(
            node_id=file_node_id,
            file=rel_path,
            line=1,
            name=os.path.basename(rel_path),
            type="def",
            category="file",
            snippet=source_lines[0] if source_lines else ""
        )
        file_nodes[rel_path] = file_node
        graph.add_node(file_node_id, **file_node.to_dict())

        definitions: List[CodeNode] = []
        references: List[Tuple[CodeNode, Optional[str]]] = []

        if rel_path.endswith(".py"):
            try:
                tree = ast.parse(content, filename=rel_path)
                visitor = PythonASTVisitor(rel_path, source_lines)
                visitor.visit(tree)
                definitions = visitor.definitions
                references = visitor.references
            except Exception as e:
                logger.warning(f"Python AST fallback to generic parser for {rel_path}: {e}")
                definitions, references = parse_generic_source(rel_path, source_lines)
        else:
            definitions, references = parse_generic_source(rel_path, source_lines)

        for def_node in definitions:
            graph.add_node(def_node.node_id, **def_node.to_dict())
            symbol_defs.setdefault(def_node.name, []).append(def_node)
            if "." in def_node.name:
                short_name = def_node.name.split(".")[-1]
                symbol_defs.setdefault(short_name, []).append(def_node)
            graph.add_edge(file_node_id, def_node.node_id, edge_type="E_contain")

        for ref_node, enc_id in references:
            all_references.append((rel_path, ref_node, enc_id))

    # Pass 2: Resolve invocation edges (E_invoke)
    total_calls = len(all_references)
    resolved_invocations = 0

    for rel_path, ref_node, enclosing_def_id in all_references:
        called_symbol = ref_node.name
        if called_symbol in BUILTIN_KEYWORDS:
            continue

        graph.add_node(ref_node.node_id, **ref_node.to_dict())

        parent_container_id = enclosing_def_id or file_nodes[rel_path].node_id
        graph.add_edge(parent_container_id, ref_node.node_id, edge_type="E_contain")

        matching_defs = symbol_defs.get(called_symbol, [])
        if matching_defs:
            for target_def in matching_defs:
                if target_def.node_id != parent_container_id:
                    graph.add_edge(ref_node.node_id, target_def.node_id, edge_type="E_invoke")
                    resolved_invocations += 1

    logger.info(f"Created {graph.number_of_nodes()} graph nodes")
    logger.info(f"Created {graph.number_of_edges()} graph edges ({resolved_invocations}/{total_calls} calls resolved to internal definitions)")
    return graph
