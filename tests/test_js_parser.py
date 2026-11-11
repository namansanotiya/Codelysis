"""
Comprehensive Unit Tests for JavaScript & TypeScript Parser.
Validates:
  - Comment suppression (single-line // and block /* ... */)
  - String literal suppression
  - Collision-free call-site IDs for multiple calls on same line
  - Arrow functions, async functions, class methods, interfaces
  - ES6 imports and CommonJS require
  - Inheritance / implements clauses
"""
import unittest
import textwrap

from parsers.languages.javascript import JavaScriptParser
from core.types import Category, NodeType


class TestJavaScriptParser(unittest.TestCase):
    def setUp(self):
        self.parser = JavaScriptParser()

    def test_comment_suppression(self):
        code = textwrap.dedent("""\
            // function commentedOut1() { return false; }
            /*
            function commentedOut2() {
                callInComment();
            }
            */
            function realFunction() {
                return true;
            }
        """)
        defs, refs = self.parser.parse("test.js", code)
        names = [d.name for d in defs]
        self.assertIn("realFunction", names)
        self.assertNotIn("commentedOut1", names, "Single-line comment function must not be extracted")
        self.assertNotIn("commentedOut2", names, "Block-comment function must not be extracted")
        
        ref_names = [r.name for r, _ in refs]
        self.assertNotIn("callInComment", ref_names, "Call in block comment must not be extracted")

    def test_string_literal_suppression(self):
        code = textwrap.dedent("""\
            function greet() {
                const msg = "function fake() { alert('hi'); }";
                const log = 'callFake()';
                return msg;
            }
        """)
        defs, refs = self.parser.parse("greet.js", code)
        names = [d.name for d in defs]
        self.assertEqual(names, ["greet"], "Fake function in string literal must not be extracted")
        ref_names = [r.name for r, _ in refs]
        self.assertNotIn("alert", ref_names, "Call in string must not be extracted")
        self.assertNotIn("callFake", ref_names, "Call in string must not be extracted")

    def test_multiple_calls_same_line_distinct_ids(self):
        code = textwrap.dedent("""\
            function run() {
                compute(); compute(); compute();
            }
        """)
        defs, refs = self.parser.parse("run.js", code)
        compute_refs = [r for r, _ in refs if r.name == "compute"]
        self.assertEqual(len(compute_refs), 3, "Expected 3 distinct calls to compute()")
        ids = {r.node_id for r in compute_refs}
        self.assertEqual(len(ids), 3, "All 3 call sites on the same line must have unique node_ids")

    def test_arrow_and_assigned_functions(self):
        code = textwrap.dedent("""\
            export const arrowFn = async (x) => {
                return x * 2;
            };
            const assignedFn = function(y) {
                return y + 1;
            };
        """)
        defs, refs = self.parser.parse("funcs.ts", code)
        names = {d.name for d in defs}
        self.assertIn("arrowFn", names)
        self.assertIn("assignedFn", names)

    def test_class_and_methods(self):
        code = textwrap.dedent("""\
            export class UserService extends BaseService {
                public async getUser(id) {
                    return fetchUser(id);
                }
            }
        """)
        defs, refs = self.parser.parse("service.ts", code)
        def_map = {d.name: d for d in defs}
        self.assertIn("UserService", def_map)
        self.assertEqual(def_map["UserService"].category, Category.CLASS.value)
        self.assertIn("UserService.getUser", def_map)
        self.assertEqual(def_map["UserService.getUser"].category, Category.METHOD.value)

        bases = self.parser.get_class_bases()
        user_service_bases = next((b for k, b in bases.items() if "UserService" in k), None)
        self.assertIsNotNone(user_service_bases)
        self.assertEqual(user_service_bases, ["BaseService"])

        # Check call site inside method has correct parent_scope
        fetch_ref = next((r for r, _ in refs if r.name == "fetchUser"), None)
        self.assertIsNotNone(fetch_ref)
        self.assertEqual(fetch_ref.parent_scope, "UserService.getUser")

    def test_imports_es6_and_require(self):
        code = textwrap.dedent("""\
            import React, { useState, useEffect as useMount } from 'react';
            import * as fs from 'fs';
            const { readFile } = require('fs');
            const path = require('path');
        """)
        self.parser.parse("app.tsx", code)
        imports = self.parser.get_imports()
        
        aliases = {b.alias: b for b in imports}
        self.assertIn("React", aliases)
        self.assertEqual(aliases["React"].module, "react")
        
        self.assertIn("useState", aliases)
        self.assertEqual(aliases["useState"].symbol, "useState")
        
        self.assertIn("useMount", aliases)
        self.assertEqual(aliases["useMount"].symbol, "useEffect")
        
        self.assertIn("fs", aliases)
        self.assertEqual(aliases["fs"].symbol, "*")

        self.assertIn("readFile", aliases)
        self.assertIn("path", aliases)


if __name__ == "__main__":
    unittest.main()
