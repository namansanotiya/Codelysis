"""
Dedicated Language Parsers for Python, JavaScript/TypeScript, Java, C/C++, Go, Rust, C#, and Generic.
"""
from parsers.languages.python import PythonParser
from parsers.languages.javascript import JavaScriptParser
from parsers.languages.java import JavaParser
from parsers.languages.cpp import CppParser
from parsers.languages.golang import GoParser
from parsers.languages.rust import RustParser
from parsers.languages.csharp import CSharpParser
from parsers.languages.generic import GenericParser

__all__ = [
    "PythonParser",
    "JavaScriptParser",
    "JavaParser",
    "CppParser",
    "GoParser",
    "RustParser",
    "CSharpParser",
    "GenericParser",
]
