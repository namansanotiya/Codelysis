"""
Parser Factory.
Selects the appropriate language parser based on file extension.
"""
import os
from typing import Dict
from parsers.base import BaseParser
from parsers.languages.python import PythonParser
from parsers.languages.javascript import JavaScriptParser
from parsers.languages.java import JavaParser
from parsers.languages.cpp import CppParser
from parsers.languages.golang import GoParser
from parsers.languages.rust import RustParser
from parsers.languages.csharp import CSharpParser
from parsers.languages.generic import GenericParser


class ParserFactory:
    _parsers: Dict[str, BaseParser] = {
        ".py": PythonParser(),
        ".js": JavaScriptParser(),
        ".jsx": JavaScriptParser(),
        ".ts": JavaScriptParser(),
        ".tsx": JavaScriptParser(),
        ".mjs": JavaScriptParser(),
        ".cjs": JavaScriptParser(),
        ".java": JavaParser(),
        ".kt": JavaParser(),
        ".c": CppParser(),
        ".cpp": CppParser(),
        ".cc": CppParser(),
        ".cxx": CppParser(),
        ".h": CppParser(),
        ".hpp": CppParser(),
        ".go": GoParser(),
        ".rs": RustParser(),
        ".cs": CSharpParser(),
    }
    _generic_fallback = GenericParser()

    @classmethod
    def get_parser(cls, file_path: str) -> BaseParser:
        """Get parser based on file extension."""
        _, ext = os.path.splitext(file_path.lower())
        return cls._parsers.get(ext, cls._generic_fallback)

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """Return all explicitly registered extensions."""
        return list(cls._parsers.keys())
