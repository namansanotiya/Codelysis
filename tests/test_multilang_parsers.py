"""
Unit tests for multi-language parsers: JS/TS, Java, C++, Go, Rust, C#, and Factory.
"""
import unittest

from parsers.factory import ParserFactory
from parsers.languages.javascript import JavaScriptParser
from parsers.languages.java import JavaParser
from parsers.languages.cpp import CppParser
from parsers.languages.golang import GoParser
from parsers.languages.rust import RustParser
from parsers.languages.csharp import CSharpParser
from parsers.filter import is_builtin_or_stdlib, extract_third_party_imports


class TestMultiLangParsers(unittest.TestCase):

    def test_factory_dispatch(self):
        self.assertIsInstance(ParserFactory.get_parser("index.js"), JavaScriptParser)
        self.assertIsInstance(ParserFactory.get_parser("App.tsx"), JavaScriptParser)
        self.assertIsInstance(ParserFactory.get_parser("Service.java"), JavaParser)
        self.assertIsInstance(ParserFactory.get_parser("main.cpp"), CppParser)
        self.assertIsInstance(ParserFactory.get_parser("server.go"), GoParser)
        self.assertIsInstance(ParserFactory.get_parser("lib.rs"), RustParser)
        self.assertIsInstance(ParserFactory.get_parser("Program.cs"), CSharpParser)

    def test_javascript_parser(self):
        js_code = """
        class AuthHandler {
            async authenticate(userToken) {
                return verifyToken(userToken);
            }
        }
        export const login = (token) => {
            return processLogin(token);
        };
        """
        parser = JavaScriptParser()
        defs, refs = parser.parse("auth.js", js_code)
        def_names = [d.name for d in defs]
        ref_names = [r[0].name for r in refs]

        self.assertIn("AuthHandler", def_names)
        self.assertIn("AuthHandler.authenticate", def_names)
        self.assertIn("login", def_names)
        self.assertIn("verifyToken", ref_names)
        self.assertIn("processLogin", ref_names)

    def test_java_parser(self):
        java_code = """
        public class PaymentService {
            public boolean processPayment(String id) {
                return validateCard(id);
            }
        }
        """
        parser = JavaParser()
        defs, refs = parser.parse("PaymentService.java", java_code)
        def_names = [d.name for d in defs]
        ref_names = [r[0].name for r in refs]

        self.assertIn("PaymentService", def_names)
        self.assertIn("PaymentService.processPayment", def_names)
        self.assertIn("validateCard", ref_names)

    def test_cpp_parser(self):
        cpp_code = """
        class DatabaseEngine {
            void executeQuery() {
                connectPool();
            }
        };
        void runServer() {
            startWorker();
        }
        """
        parser = CppParser()
        defs, refs = parser.parse("db.cpp", cpp_code)
        def_names = [d.name for d in defs]
        ref_names = [r[0].name for r in refs]

        self.assertIn("DatabaseEngine", def_names)
        self.assertIn("runServer", def_names)
        self.assertIn("connectPool", ref_names)
        self.assertIn("startWorker", ref_names)

    def test_go_parser(self):
        go_code = """
        type UserService struct {}

        func (u *UserService) GetUser(id string) {
            fetchUserDb(id)
        }

        func InitApp() {
            setupRouter()
        }
        """
        parser = GoParser()
        defs, refs = parser.parse("user.go", go_code)
        def_names = [d.name for d in defs]
        ref_names = [r[0].name for r in refs]

        self.assertIn("UserService", def_names)
        self.assertIn("UserService.GetUser", def_names)
        self.assertIn("InitApp", def_names)
        self.assertIn("fetchUserDb", ref_names)
        self.assertIn("setupRouter", ref_names)

    def test_rust_parser(self):
        rust_code = """
        struct TokenManager {}

        impl TokenManager {
            pub fn validate(&self) {
                check_signature();
            }
        }

        fn run() {
            start_daemon();
        }
        """
        parser = RustParser()
        defs, refs = parser.parse("token.rs", rust_code)
        def_names = [d.name for d in defs]
        ref_names = [r[0].name for r in refs]

        self.assertIn("TokenManager", def_names)
        self.assertIn("TokenManager::validate", def_names)
        self.assertIn("run", def_names)
        self.assertIn("check_signature", ref_names)
        self.assertIn("start_daemon", ref_names)

    def test_filter(self):
        self.assertTrue(is_builtin_or_stdlib("print", "python"))
        self.assertTrue(is_builtin_or_stdlib("console", "javascript"))
        self.assertTrue(is_builtin_or_stdlib("System", "java"))
        self.assertTrue(is_builtin_or_stdlib("fmt", "golang"))
        self.assertTrue(is_builtin_or_stdlib("println", "rust"))
        self.assertFalse(is_builtin_or_stdlib("customFunction", "python"))


if __name__ == "__main__":
    unittest.main()
