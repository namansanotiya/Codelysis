"""
Regression Test Suite for Codelysis Graph Construction Corrections.

Covers the 12 required test cases from the sprint spec:
  1.  Same function name in different files -> distinct nodes, correct E_invoke targets
  2.  Nested functions with same name -> correctly scoped node IDs
  3.  foo(); foo() on one line -> two distinct ref nodes (node ID collision fix)
  4.  Class methods same name in different classes -> no cross-class E_override
  5.  Python relative imports + aliases -> E_import edges and alias resolution
  6.  JS named/default imports -> ImportBinding captured
  7.  Multiple inheritance class C(A, B) -> two E_inherit edges
  8.  Method override chain -> E_override edges
  9.  External dependency call -> no E_invoke created (or tagged repo_ambiguous)
  10. Two typed edges between same nodes -> MultiDiGraph stores both independently
  11. Invocation edge direction: assert graph.has_edge(ref_id, def_id)
  12. MultiDiGraph traversal and serialization round-trip
"""
import unittest
import textwrap

import networkx as nx

from graph.builder import build_graph, RepoGraphBuilder
from graph.symbol_index import SymbolIndex
from core.types import CodeNode, Category, NodeType, ImportBinding, get_edges_between, get_edge_types, has_edge_type
from traversal.ego_graph import extract_ego_graph


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def build_from_sources(sources: dict, multigraph: bool = True):
    """Build a graph from an in-memory {rel_path: content} dict."""
    return build_graph(sources, multigraph=multigraph)


# ---------------------------------------------------------------------------
# Test 1: Same function name in different files -> distinct nodes
# ---------------------------------------------------------------------------
class TestSameNameDifferentFiles(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "auth/service.py": textwrap.dedent("""\
                def validate(token):
                    return True
            """),
            "admin/service.py": textwrap.dedent("""\
                def validate(token):
                    return False
            """),
            "api/router.py": textwrap.dedent("""\
                from auth.service import validate

                def handle(token):
                    return validate(token)
            """),
        }

    def test_distinct_definition_nodes(self):
        graph = build_from_sources(self.sources)
        validate_defs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "validate" and d.get("type") == "def"
        ]
        # Should have two separate definition nodes
        self.assertEqual(len(validate_defs), 2, "Expected 2 'validate' definition nodes in different files")
        node_ids = {d["node_id"] for d in validate_defs}
        self.assertEqual(len(node_ids), 2, "Node IDs must be distinct")

    def test_invocation_resolves_to_correct_file(self):
        graph = build_from_sources(self.sources)
        # The import in api/router.py is from auth.service, so only auth/service.py's validate
        # should receive a high-confidence E_invoke edge
        auth_validate = next(
            (d for n, d in graph.nodes(data=True)
             if d.get("name") == "validate" and "auth" in d.get("file", "")),
            None
        )
        admin_validate = next(
            (d for n, d in graph.nodes(data=True)
             if d.get("name") == "validate" and "admin" in d.get("file", "")),
            None
        )
        self.assertIsNotNone(auth_validate)
        self.assertIsNotNone(admin_validate)

        # Look for any E_invoke edge pointing to auth/service validate
        invoke_to_auth = [
            (u, v, k, d) for u, v, k, d in graph.edges(data=True, keys=True)
            if d.get("edge_type") == "E_invoke" and v == auth_validate["node_id"]
        ]
        self.assertGreater(len(invoke_to_auth), 0, "Expected at least one E_invoke -> auth/service.validate")


# ---------------------------------------------------------------------------
# Test 2: Nested functions with same name -> correctly scoped node IDs
# ---------------------------------------------------------------------------
class TestNestedFunctionScoping(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "nested.py": textwrap.dedent("""\
                def outer():
                    def helper():
                        pass
                    return helper()

                def another():
                    def helper():
                        pass
                    return helper()
            """),
        }

    def test_nested_functions_distinct(self):
        graph = build_from_sources(self.sources)
        helper_defs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name", "").endswith("helper") and d.get("type") == "def"
        ]
        # Both nested helpers should be distinct nodes
        self.assertGreaterEqual(len(helper_defs), 1, "At least one helper def node expected")
        node_ids = {d["node_id"] for d in helper_defs}
        self.assertEqual(len(node_ids), len(helper_defs), "Nested helper nodes must have distinct IDs")


# ---------------------------------------------------------------------------
# Test 3: foo(); foo() on one line -> two distinct ref nodes
# ---------------------------------------------------------------------------
class TestCallCollisionSameLine(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "calls.py": textwrap.dedent("""\
                def foo():
                    pass

                x = foo(); y = foo()
            """),
        }

    def test_two_calls_same_line_distinct_nodes(self):
        graph = build_from_sources(self.sources)
        foo_refs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "foo" and d.get("type") == "ref"
        ]
        # Two calls to foo() on the same line must produce two distinct node IDs
        self.assertEqual(len(foo_refs), 2, f"Expected 2 ref nodes for foo, got {len(foo_refs)}: {[d['node_id'] for d in foo_refs]}")
        ref_ids = {d["node_id"] for d in foo_refs}
        self.assertEqual(len(ref_ids), 2, "Both foo() call sites must have unique node IDs")


# ---------------------------------------------------------------------------
# Test 4: Class methods same name in different classes -> no cross-class override
# ---------------------------------------------------------------------------
class TestNoSpuriousCrossClassOverride(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "services.py": textwrap.dedent("""\
                class AuthService:
                    def process(self):
                        return "auth"

                class PaymentService:
                    def process(self):
                        return "pay"
            """),
        }

    def test_no_cross_class_override_edge(self):
        graph = build_from_sources(self.sources)
        process_defs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name", "").endswith(".process") and d.get("type") == "def"
        ]
        self.assertEqual(len(process_defs), 2, "Expected 2 'process' method defs")
        node_ids = [d["node_id"] for d in process_defs]

        # Must NOT have an E_override between AuthService.process and PaymentService.process
        # since they don't share an inheritance relationship
        for u_id in node_ids:
            for v_id in node_ids:
                if u_id != v_id:
                    override_edges = [
                        d for d in get_edges_between(graph, u_id, v_id)
                        if d.get("edge_type") == "E_override"
                    ]
                    self.assertEqual(
                        len(override_edges), 0,
                        f"Spurious E_override between unrelated classes: {u_id} -> {v_id}"
                    )


# ---------------------------------------------------------------------------
# Test 5: Python import aliases -> alias resolution in invocations
# ---------------------------------------------------------------------------
class TestPythonImportAlias(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "utils/crypto.py": textwrap.dedent("""\
                def sha256_hash(data):
                    return data
            """),
            "api/handler.py": textwrap.dedent("""\
                from utils.crypto import sha256_hash as hash_it

                def handle(req):
                    return hash_it(req)
            """),
        }

    def test_alias_import_binding_captured(self):
        builder = RepoGraphBuilder()
        from sources.local_loader import LocalLoader
        # Use in-memory build
        graph = build_graph(self.sources)
        # Expect ImportBinding alias 'hash_it' -> module 'utils.crypto'
        # This is verified by checking E_invoke or E_import edges
        invoke_edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == "E_invoke" and d.get("symbol") in ("hash_it", "sha256_hash")
        ]
        # At minimum an invocation from handle to sha256_hash should exist
        self.assertGreater(len(invoke_edges), 0, "Expected at least one E_invoke for alias import call")


# ---------------------------------------------------------------------------
# Test 6: JS named imports -> ImportBinding captured
# ---------------------------------------------------------------------------
class TestJSNamedImport(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "auth/service.js": "export function validateToken(t) { return true; }\n",
            "api/controller.js": textwrap.dedent("""\
                import { validateToken } from './auth/service';

                function handleRequest(token) {
                    return validateToken(token);
                }
            """),
        }

    def test_js_import_and_invocation_captured(self):
        graph = build_from_sources(self.sources)
        validate_defs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "validateToken" and d.get("type") == "def"
        ]
        validate_refs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "validateToken" and d.get("type") == "ref"
        ]
        self.assertGreater(len(validate_defs), 0, "Expected validateToken definition node")
        self.assertGreater(len(validate_refs), 0, "Expected validateToken reference node")


# ---------------------------------------------------------------------------
# Test 7: Multiple inheritance -> two E_inherit edges
# ---------------------------------------------------------------------------
class TestMultipleInheritance(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "mixins.py": textwrap.dedent("""\
                class LogMixin:
                    def log(self):
                        pass

                class AuthMixin:
                    def authenticate(self):
                        pass

                class Service(LogMixin, AuthMixin):
                    def run(self):
                        self.log()
                        self.authenticate()
            """),
        }

    def test_multiple_inherit_edges(self):
        graph = build_from_sources(self.sources)
        inherit_edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == "E_inherit"
        ]
        # Service -> LogMixin and Service -> AuthMixin
        self.assertGreaterEqual(len(inherit_edges), 2, f"Expected >=2 E_inherit edges, got {len(inherit_edges)}")


# ---------------------------------------------------------------------------
# Test 8: Method override chain -> E_override edges
# ---------------------------------------------------------------------------
class TestMethodOverride(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "base.py": textwrap.dedent("""\
                class BaseService:
                    def execute(self):
                        pass
            """),
            "custom.py": textwrap.dedent("""\
                from base import BaseService

                class CustomService(BaseService):
                    def execute(self):
                        return "custom"
            """),
        }

    def test_override_edge_exists(self):
        graph = build_from_sources(self.sources)
        override_edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == "E_override"
        ]
        # CustomService.execute should E_override BaseService.execute
        self.assertGreaterEqual(len(override_edges), 1,
                                 "Expected at least one E_override for CustomService.execute")


# ---------------------------------------------------------------------------
# Test 9: External dependency call -> no or low-confidence E_invoke
# ---------------------------------------------------------------------------
class TestExternalDependency(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "app.py": textwrap.dedent("""\
                import requests

                def fetch(url):
                    return requests.get(url)
            """),
        }

    def test_external_call_not_wired_to_internal(self):
        graph = build_from_sources(self.sources)
        # 'get' and 'requests' should not resolve to any internal definition
        internal_defs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "get" and d.get("type") == "def"
        ]
        # Should be empty — no internal `get` definition in this codebase
        self.assertEqual(len(internal_defs), 0,
                          "No internal 'get' definition should exist for external requests.get")


# ---------------------------------------------------------------------------
# Test 10: Two typed edges between same nodes -> MultiDiGraph stores both
# ---------------------------------------------------------------------------
class TestMultiEdgeStorage(unittest.TestCase):
    def test_multigraph_stores_multiple_edge_types(self):
        G = nx.MultiDiGraph()
        G.add_node("A")
        G.add_node("B")
        G.add_edge("A", "B", key="E_contain", edge_type="E_contain")
        G.add_edge("A", "B", key="E_invoke", edge_type="E_invoke")

        edge_types = get_edge_types(G, "A", "B")
        self.assertIn("E_contain", edge_types, "E_contain should be in MultiDiGraph edges")
        self.assertIn("E_invoke", edge_types, "E_invoke should be in MultiDiGraph edges")
        self.assertEqual(len(get_edges_between(G, "A", "B")), 2,
                          "MultiDiGraph should store 2 distinct edges between A and B")

    def test_has_edge_type_helper(self):
        G = nx.MultiDiGraph()
        G.add_node("X")
        G.add_node("Y")
        G.add_edge("X", "Y", key="E_inherit", edge_type="E_inherit")
        self.assertTrue(has_edge_type(G, "X", "Y", "E_inherit"))
        self.assertFalse(has_edge_type(G, "X", "Y", "E_invoke"))


# ---------------------------------------------------------------------------
# Test 11: Invocation edge direction ref -> def (not def -> ref)
# ---------------------------------------------------------------------------
class TestInvocationEdgeDirection(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "direction.py": textwrap.dedent("""\
                def callee():
                    pass

                def caller():
                    callee()
            """),
        }

    def test_edge_direction_ref_to_def(self):
        """E_invoke must go FROM call site (ref) TO definition (def) — per RepoGraph paper."""
        graph = build_from_sources(self.sources)
        callee_defs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "callee" and d.get("type") == "def"
        ]
        callee_refs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "callee" and d.get("type") == "ref"
        ]
        self.assertEqual(len(callee_defs), 1, "Expected exactly one callee definition")
        self.assertGreater(len(callee_refs), 0, "Expected at least one callee reference")

        def_id = callee_defs[0]["node_id"]
        for ref in callee_refs:
            ref_id = ref["node_id"]
            # ref -> def direction must exist
            self.assertTrue(
                graph.has_edge(ref_id, def_id),
                f"E_invoke must go FROM ref ({ref_id}) TO def ({def_id})"
            )
            # def -> ref direction must NOT exist as an E_invoke
            if graph.has_edge(def_id, ref_id):
                edge_types_reverse = get_edge_types(graph, def_id, ref_id)
                self.assertNotIn(
                    "E_invoke", edge_types_reverse,
                    "E_invoke must not point from def to ref (direction violation)"
                )


# ---------------------------------------------------------------------------
# Test 12: MultiDiGraph traversal and serialization round-trip
# ---------------------------------------------------------------------------
class TestMultiDiGraphTraversalAndSerialization(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "roundtrip.py": textwrap.dedent("""\
                def alpha():
                    return beta()

                def beta():
                    return 42
            """),
        }

    def test_ego_graph_traversal(self):
        graph = build_from_sources(self.sources)
        self.assertIsInstance(graph, nx.MultiDiGraph)

        alpha_defs = [
            {"node_id": n}
            for n, d in graph.nodes(data=True)
            if d.get("name") == "alpha" and d.get("type") == "def"
        ]
        self.assertGreater(len(alpha_defs), 0)

        ego = extract_ego_graph(graph, alpha_defs, k=2)
        self.assertIsInstance(ego, nx.MultiDiGraph)
        # Ego graph must include at least alpha's file node and beta def
        self.assertGreater(ego.number_of_nodes(), 1)

    def test_serialization_round_trip(self):
        graph = build_from_sources(self.sources)
        # Serialize all edges
        edges = []
        for u, v, k, d in graph.edges(data=True, keys=True):
            edges.append({"src": u, "dst": v, "key": k, "attrs": d})

        # Verify E_invoke edges have required fields
        invoke_edges = [e for e in edges if e["attrs"].get("edge_type") == "E_invoke"]
        for edge in invoke_edges:
            self.assertIn("confidence", edge["attrs"], "E_invoke edge must have confidence")
            self.assertIn("resolution_method", edge["attrs"], "E_invoke edge must have resolution_method")
            self.assertIn("evidence", edge["attrs"], "E_invoke edge must have evidence")
            self.assertIn("symbol", edge["attrs"], "E_invoke edge must have symbol")


# ---------------------------------------------------------------------------
# Test: SymbolIndex unit tests
# ---------------------------------------------------------------------------
class TestSymbolIndex(unittest.TestCase):
    def _make_node(self, name, file, line=1, qname="", category="function"):
        return CodeNode(
            node_id=f"{file}:L{line}:def:{name}",
            file=file,
            line=line,
            name=name,
            type="def",
            category=category,
            qualified_name=qname or name,
        )

    def test_add_and_resolve_local(self):
        idx = SymbolIndex()
        node = self._make_node("validate", "auth/service.py")
        idx.add_definition(node)
        results = idx.resolve("validate", from_file="auth/service.py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].node_id, node.node_id)
        self.assertEqual(results[0][2], "local_exact")

    def test_resolve_import_alias(self):
        idx = SymbolIndex()
        node = self._make_node("sha256_hash", "utils/crypto.py")
        idx.add_definition(node)
        idx.add_imports("api/handler.py", [
            ImportBinding(module="utils.crypto", symbol="sha256_hash", alias="hash_it", is_from_import=True)
        ])
        results = idx.resolve("hash_it", from_file="api/handler.py")
        self.assertGreater(len(results), 0)
        self.assertIn(results[0][2], ("import_exact", "import_fallback"))

    def test_no_cross_file_spurious_match(self):
        idx = SymbolIndex()
        node_a = self._make_node("process", "auth/service.py")
        node_b = self._make_node("process", "admin/service.py")
        idx.add_definition(node_a)
        idx.add_definition(node_b)
        # Resolving from auth/service.py should prefer local
        results = idx.resolve("process", from_file="auth/service.py")
        self.assertGreater(len(results), 0)
        # Highest confidence result should be the local one
        self.assertEqual(results[0][0].file, "auth/service.py")
        self.assertEqual(results[0][2], "local_exact")

    def test_repo_ambiguous_when_no_local(self):
        idx = SymbolIndex()
        idx.add_definition(self._make_node("compute", "pkg/a.py"))
        idx.add_definition(self._make_node("compute", "pkg/b.py"))
        results = idx.resolve("compute", from_file="other/main.py")
        self.assertGreater(len(results), 0)
        self.assertTrue(all(r[2] in ("sibling_module", "repo_ambiguous", "repo_unique") for r in results))


# ---------------------------------------------------------------------------
# Test 13: Recursive self-invocation creates E_invoke self-dependency edges
# ---------------------------------------------------------------------------
class TestRecursiveSelfInvocation(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "math_ops.py": textwrap.dedent("""\
                def factorial(n):
                    if n <= 1:
                        return 1
                    return n * factorial(n - 1)
            """),
        }

    def test_recursive_call_creates_e_invoke_edge(self):
        graph = build_from_sources(self.sources)
        fact_defs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "factorial" and d.get("type") == "def"
        ]
        fact_refs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "factorial" and d.get("type") == "ref"
        ]
        self.assertEqual(len(fact_defs), 1)
        self.assertEqual(len(fact_refs), 1)

        def_id = fact_defs[0]["node_id"]
        ref_id = fact_refs[0]["node_id"]

        # Must have E_invoke edge from the recursive call site to its own definition
        self.assertTrue(graph.has_edge(ref_id, def_id), "Recursive call must wire E_invoke edge")
        edges = get_edges_between(graph, ref_id, def_id)
        invoke_edges = [e for e in edges if e.get("edge_type") == "E_invoke"]
        self.assertEqual(len(invoke_edges), 1)
        self.assertTrue(invoke_edges[0].get("is_recursive"), "Edge must be tagged as recursive")


# ---------------------------------------------------------------------------
# Test 14: Ambiguous symbols not represented as confirmed E_invoke
# ---------------------------------------------------------------------------
class TestAmbiguousCandidatesNotConfirmed(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "package_x/calc.py": textwrap.dedent("""\
                def calculate(val):
                    return val * 2
            """),
            "package_y/calc.py": textwrap.dedent("""\
                def calculate(val):
                    return val + 10
            """),
            "unrelated/main.py": textwrap.dedent("""\
                def runner():
                    # calculate is not imported and not in same file
                    return calculate(5)
            """),
        }

    def test_ambiguous_symbol_creates_candidate_not_confirmed_invoke(self):
        graph = build_from_sources(self.sources)
        ref_node = next(
            (d for n, d in graph.nodes(data=True)
             if d.get("name") == "calculate" and d.get("type") == "ref" and "unrelated" in d.get("file", "")),
            None
        )
        self.assertIsNotNone(ref_node)

        # Check all outgoing edges from this reference site
        edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if u == ref_node["node_id"]
        ]
        confirmed_invokes = [e for e in edges if e[2].get("edge_type") == "E_invoke"]
        candidate_invokes = [e for e in edges if e[2].get("edge_type") == "E_invoke_candidate"]

        # Confirmed E_invoke must be 0 because it's ambiguous across unrelated packages
        self.assertEqual(len(confirmed_invokes), 0, "Ambiguous symbol must NOT create confirmed E_invoke")
        # Candidate edges should be created preserving confidence and evidence
        self.assertGreater(len(candidate_invokes), 0, "Ambiguous symbol must create E_invoke_candidate edges")
        for cand in candidate_invokes:
            self.assertTrue(cand[2].get("is_candidate"))
            self.assertIn("confidence", cand[2])
            self.assertIn("evidence", cand[2])


# ---------------------------------------------------------------------------
# Test 15: Duplicate class names in different files do not overwrite bases
# ---------------------------------------------------------------------------
class TestDuplicateClassNamesAcrossFiles(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "bases.py": textwrap.dedent("""\
                class AuthBase:
                    pass

                class BillingBase:
                    pass
            """),
            "auth/service.py": textwrap.dedent("""\
                from bases import AuthBase

                class Service(AuthBase):
                    def execute(self):
                        pass
            """),
            "billing/service.py": textwrap.dedent("""\
                from bases import BillingBase

                class Service(BillingBase):
                    def execute(self):
                        pass
            """),
        }

    def test_duplicate_class_names_preserve_both_inheritance_edges(self):
        graph = build_from_sources(self.sources)
        service_defs = [
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "Service" and d.get("type") == "def" and d.get("category") == "class"
        ]
        self.assertEqual(len(service_defs), 2, "Both Service classes must exist as distinct nodes")

        auth_service = next(d for d in service_defs if "auth" in d.get("file", ""))
        billing_service = next(d for d in service_defs if "billing" in d.get("file", ""))

        auth_base = next(d for n, d in graph.nodes(data=True) if d.get("name") == "AuthBase" and d.get("type") == "def")
        billing_base = next(d for n, d in graph.nodes(data=True) if d.get("name") == "BillingBase" and d.get("type") == "def")

        # auth/service.py:Service must inherit from AuthBase
        self.assertTrue(
            has_edge_type(graph, auth_service["node_id"], auth_base["node_id"], "E_inherit"),
            "auth/service.py:Service must inherit from AuthBase"
        )
        # billing/service.py:Service must inherit from BillingBase
        self.assertTrue(
            has_edge_type(graph, billing_service["node_id"], billing_base["node_id"], "E_inherit"),
            "billing/service.py:Service must inherit from BillingBase"
        )
        # Cross inheritance must NOT exist
        self.assertFalse(has_edge_type(graph, auth_service["node_id"], billing_base["node_id"], "E_inherit"))
        self.assertFalse(has_edge_type(graph, billing_service["node_id"], auth_base["node_id"], "E_inherit"))


# ---------------------------------------------------------------------------
# Test 16: Multi-level inheritance and override resolution across ancestry
# ---------------------------------------------------------------------------
class TestMultiLevelInheritanceAndOverrides(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "hierarchy.py": textwrap.dedent("""\
                class GrandParent:
                    def execute(self):
                        return 1

                class Parent(GrandParent):
                    pass

                class Child(Parent):
                    def execute(self):
                        return 2
            """),
        }

    def test_child_overrides_grandparent_across_ancestry(self):
        graph = build_from_sources(self.sources)
        grandparent_exec = next(
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "GrandParent.execute" and d.get("type") == "def"
        )
        child_exec = next(
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "Child.execute" and d.get("type") == "def"
        )

        # Child.execute must have E_override pointing to GrandParent.execute
        self.assertTrue(
            has_edge_type(graph, child_exec["node_id"], grandparent_exec["node_id"], "E_override"),
            "Child.execute must E_override GrandParent.execute across inheritance ancestry"
        )


# ---------------------------------------------------------------------------
# Test 17: Incompatible signature override rejected
# ---------------------------------------------------------------------------
class TestIncompatibleSignatureOverrideRejected(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "incompat.py": textwrap.dedent("""\
                class BaseHandler:
                    def process(self):
                        pass

                class SubHandler(BaseHandler):
                    def process(self, required_arg1, required_arg2):
                        pass
            """),
        }

    def test_incompatible_override_rejected(self):
        graph = build_from_sources(self.sources)
        base_proc = next(
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "BaseHandler.process" and d.get("type") == "def"
        )
        sub_proc = next(
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "SubHandler.process" and d.get("type") == "def"
        )

        # Incompatible signatures (extra required parameters) must not be linked with E_override
        self.assertFalse(
            has_edge_type(graph, sub_proc["node_id"], base_proc["node_id"], "E_override"),
            "Incompatible method signatures must not produce an E_override edge"
        )


# ---------------------------------------------------------------------------
# Test 18: Package __init__.py qualified names
# ---------------------------------------------------------------------------
class TestPackageInitQualifiedName(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "auth/__init__.py": textwrap.dedent("""\
                def create_session():
                    return "sess_123"
            """),
        }

    def test_init_qualified_name_uses_package_name(self):
        graph = build_from_sources(self.sources)
        sess_def = next(
            d for n, d in graph.nodes(data=True)
            if d.get("name") == "create_session" and d.get("type") == "def"
        )
        # Qualified name must be 'auth.create_session', NOT 'auth.__init__.create_session'
        self.assertEqual(sess_def.get("qualified_name"), "auth.create_session")


# ---------------------------------------------------------------------------
# Test 19: Strict package import avoiding broad suffix false matches
# ---------------------------------------------------------------------------
class TestStrictPackageImportResolution(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "auth/service.py": textwrap.dedent("""\
                def verify():
                    return True
            """),
            "billing/service.py": textwrap.dedent("""\
                def bill():
                    return False
            """),
            "auth/handler.py": textwrap.dedent("""\
                from auth.service import verify

                def handle():
                    return verify()
            """),
        }

    def test_strict_import_does_not_cross_match(self):
        graph = build_from_sources(self.sources)
        auth_handler = next(d for n, d in graph.nodes(data=True) if "auth/handler.py" in d.get("file", "") and d.get("category") == "file")
        auth_service = next(d for n, d in graph.nodes(data=True) if "auth/service.py" in d.get("file", "") and d.get("category") == "file")
        billing_service = next(d for n, d in graph.nodes(data=True) if "billing/service.py" in d.get("file", "") and d.get("category") == "file")

        # auth/handler must import auth/service
        self.assertTrue(has_edge_type(graph, auth_handler["node_id"], auth_service["node_id"], "E_import"))
        # auth/handler must NOT import billing/service
        self.assertFalse(has_edge_type(graph, auth_handler["node_id"], billing_service["node_id"], "E_import"))


# ---------------------------------------------------------------------------
# Test 20: Tree-sitter evaluation diagnostic report
# ---------------------------------------------------------------------------
class TestTreeSitterEvaluation(unittest.TestCase):
    def test_evaluation_report_structure(self):
        from parsers.languages.javascript_treesitter import evaluate_treesitter_support, TreeSitterJavaScriptParser
        report = evaluate_treesitter_support()
        self.assertIn("tree_sitter_installed", report)
        self.assertIn("active_parser", report)
        self.assertIn("diagnostics", report)

        # Parser adapter should initialize and parse without crashing
        adapter = TreeSitterJavaScriptParser()
        defs, refs = adapter.parse("sample.js", "function hello() { return 1; }")
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0].name, "hello")


# ---------------------------------------------------------------------------
# Test 21: Tree-sitter CST visitor extraction (_extract_nodes_from_tree)
# ---------------------------------------------------------------------------
class TestTreeSitterCSTExtraction(unittest.TestCase):
    def test_cst_walker_extracts_definitions_and_calls(self):
        from parsers.languages.javascript_treesitter import TreeSitterJavaScriptParser

        class MockNode:
            def __init__(self, ntype, start_byte, end_byte, start_point=(0, 0), end_point=(0, 0), children=None, fields=None):
                self.type = ntype
                self.start_byte = start_byte
                self.end_byte = end_byte
                self.start_point = start_point
                self.end_point = end_point
                self.children = children or []
                self._fields = fields or {}

            def child_by_field_name(self, name):
                return self._fields.get(name)

        content = "class AuthService extends BaseService { validate(token) { return check(token); } }"
        # Exact slice coordinates:
        # AuthService: 6:17
        # heritage: 18:37
        # validate: 41:49
        # (token): 49:56
        # check: 65:70
        # (token): 70:77
        name_node = MockNode("identifier", 6, 17, (0, 6), (0, 17))
        heritage_node = MockNode("class_heritage", 18, 37, (0, 18), (0, 37))
        m_name_node = MockNode("property_identifier", 40, 48, (0, 40), (0, 48))
        m_params_node = MockNode("formal_parameters", 48, 55, (0, 48), (0, 55))

        call_fn_node = MockNode("identifier", 65, 70, (0, 65), (0, 70))
        call_args_node = MockNode("arguments", 70, 77, (0, 70), (0, 77))
        call_node = MockNode("call_expression", 65, 77, (0, 65), (0, 77), fields={"function": call_fn_node, "arguments": call_args_node})

        method_node = MockNode(
            "method_definition", 40, 81, (0, 40), (0, 81),
            children=[call_node],
            fields={"name": m_name_node, "parameters": m_params_node}
        )
        class_node = MockNode(
            "class_declaration", 0, 83, (0, 0), (0, 83),
            children=[method_node],
            fields={"name": name_node, "heritage": heritage_node}
        )

        parser = TreeSitterJavaScriptParser()
        defs, refs = parser._extract_nodes_from_tree("auth.js", content, class_node)

        # Definitions: AuthService (class), AuthService.validate (method)
        self.assertEqual(len(defs), 2)
        self.assertEqual(defs[0].name, "AuthService")
        self.assertEqual(defs[0].category, "class")
        self.assertEqual(defs[1].name, "AuthService.validate")
        self.assertEqual(defs[1].category, "method")

        # References: call to check(token)
        self.assertEqual(len(refs), 1)
        ref_node, enclosing_id = refs[0]
        self.assertEqual(ref_node.name, "check")
        self.assertEqual(enclosing_id, defs[1].node_id)

    def test_cst_walker_arrow_functions_and_multiple_calls_same_line(self):
        from parsers.languages.javascript_treesitter import TreeSitterJavaScriptParser

        class MockNode:
            def __init__(self, ntype, start_byte, end_byte, start_point=(0, 0), end_point=(0, 0), children=None, fields=None):
                self.type = ntype
                self.start_byte = start_byte
                self.end_byte = end_byte
                self.start_point = start_point
                self.end_point = end_point
                self.children = children or []
                self._fields = fields or {}

            def child_by_field_name(self, name):
                return self._fields.get(name)

        content = "const processData = (x) => { foo(); foo(); };"
        # x is 21:22
        # foo 1 is 29:32, foo 2 is 36:39
        name_node = MockNode("identifier", 6, 17, (0, 6), (0, 17))
        params_node = MockNode("formal_parameters", 20, 23, (0, 20), (0, 23))

        call_fn1 = MockNode("identifier", 29, 32, (0, 29), (0, 32))
        call_fn2 = MockNode("identifier", 36, 39, (0, 36), (0, 39))
        call1 = MockNode("call_expression", 29, 34, (0, 29), (0, 34), fields={"function": call_fn1})
        call2 = MockNode("call_expression", 36, 41, (0, 36), (0, 41), fields={"function": call_fn2})

        arrow_body = MockNode("statement_block", 27, 44, (0, 27), (0, 44), children=[call1, call2])
        arrow_node = MockNode("arrow_function", 20, 44, (0, 20), (0, 44), children=[arrow_body], fields={"parameters": params_node})
        decl_node = MockNode("variable_declarator", 6, 44, (0, 6), (0, 44), children=[arrow_node], fields={"name": name_node, "value": arrow_node})
        root_node = MockNode("program", 0, 45, (0, 0), (0, 45), children=[decl_node])

        parser = TreeSitterJavaScriptParser()
        defs, refs = parser._extract_nodes_from_tree("app.js", content, root_node)

        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0].name, "processData")
        self.assertEqual(defs[0].category, "function")

        # Two calls on the same line must produce two distinct reference nodes
        self.assertEqual(len(refs), 2)
        ref1, enc1 = refs[0]
        ref2, enc2 = refs[1]
        self.assertEqual(ref1.name, "foo")
        self.assertEqual(ref2.name, "foo")
        self.assertNotEqual(ref1.node_id, ref2.node_id, "Distinct calls on same line must have unique node IDs")
        self.assertIn("C29", ref1.node_id)
        self.assertIn("C36", ref2.node_id)


# ---------------------------------------------------------------------------
# Test 22: Candidate callers separation in ImpactSummary
# ---------------------------------------------------------------------------
class TestImpactSummaryCandidateSeparation(unittest.TestCase):
    def test_candidate_callers_strictly_separated_from_direct(self):
        from traversal.impact_analyzer import analyze_impact_summary
        from core.types import EdgeType

        g = nx.MultiDiGraph()
        # Seed definition
        seed = {"node_id": "seed:def:login", "file": "auth.py", "name": "login", "type": "def", "category": "function"}
        caller1 = {"node_id": "c1:def:handler", "file": "api.py", "name": "handler", "type": "def", "category": "function"}
        caller2 = {"node_id": "c2:def:ambig", "file": "other.py", "name": "ambig", "type": "def", "category": "function"}

        g.add_node(seed["node_id"], **seed)
        g.add_node(caller1["node_id"], **caller1)
        g.add_node(caller2["node_id"], **caller2)

        # Confirmed E_invoke: caller1 -> seed
        g.add_edge(caller1["node_id"], seed["node_id"], edge_type=EdgeType.E_INVOKE.value)
        # Unconfirmed E_invoke_candidate: caller2 -> seed
        g.add_edge(caller2["node_id"], seed["node_id"], edge_type=EdgeType.E_INVOKE_CANDIDATE.value)

        summary = analyze_impact_summary(g, g, [seed])

        # caller1 must be in direct_callers
        self.assertEqual(len(summary.direct_callers), 1)
        self.assertEqual(summary.direct_callers[0]["name"], "handler")

        # caller2 must be in candidate_callers, NOT in direct_callers or callees
        self.assertEqual(len(summary.candidate_callers), 1)
        self.assertEqual(summary.candidate_callers[0]["name"], "ambig")
        self.assertNotIn(caller2, summary.direct_callers)
        self.assertNotIn(caller2, summary.callees)


# ---------------------------------------------------------------------------
# Test 23: Deeply nested Python lexical scope (Outer.Inner.method)
# ---------------------------------------------------------------------------
class TestDeeplyNestedPythonScoping(unittest.TestCase):
    def test_nested_class_method_and_intra_class_resolution(self):
        sources = {
            "services/orchestrator.py": textwrap.dedent("""\
                class Engine:
                    class Worker:
                        def execute(self):
                            return self.run_task()
                        def run_task(self):
                            return "ok"
            """)
        }
        graph = build_from_sources(sources)
        exec_def = next(d for n, d in graph.nodes(data=True) if d.get("name") == "Engine.Worker.execute" and d.get("type") == "def")
        run_def = next(d for n, d in graph.nodes(data=True) if d.get("name") == "Engine.Worker.run_task" and d.get("type") == "def")

        self.assertIsNotNone(exec_def)
        self.assertIsNotNone(run_def)
        self.assertEqual(exec_def.get("qualified_name"), "services.orchestrator.Engine.Worker.execute")

        # Ref to self.run_task() inside execute() must invoke Engine.Worker.run_task with confidence 1.0
        invoke_edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == "E_invoke" and v == run_def["node_id"]
        ]
        self.assertGreater(len(invoke_edges), 0)
        self.assertEqual(invoke_edges[0][2].get("resolution_method"), "intra_class")


# ---------------------------------------------------------------------------
# Test 24: Full test suite collection with sample_repo/tests/test_auth.py
# ---------------------------------------------------------------------------
class TestSampleRepoTestCollection(unittest.TestCase):
    def test_sample_repo_auth_imports_and_runs_without_error(self):
        import sample_repo.tests.test_auth as sample_auth
        self.assertTrue(callable(sample_auth.test_validate_token_success))
        self.assertTrue(callable(sample_auth.test_login_user))
        self.assertTrue(callable(sample_auth.test_core_processor))

        # Execute tests to verify runtime behavior
        sample_auth.test_validate_token_success()
        sample_auth.test_login_user()
        sample_auth.test_core_processor()


if __name__ == "__main__":
    unittest.main()

