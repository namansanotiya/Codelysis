"""
Configuration settings for Graph-RAG Code Change Impact Analysis & Co-Change Recommender.
Supports Multi-Language Repositories (Python, JS/TS, Java, C/C++, Go).
"""
import os
import sys

# Number of graph hops for ego-subgraph extraction
K_HOPS: int = 2

# Supported file extensions for multi-language AST / symbol analysis
SUPPORTED_EXTENSIONS: list[str] = [
    ".py",                  # Python
    ".js", ".jsx",          # JavaScript
    ".ts", ".tsx",          # TypeScript
    ".java",                # Java
    ".c", ".cpp", ".h", ".hpp", # C / C++
    ".go"                   # Go
]

# Default LLM Model to use via Google GenAI or OpenAI
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")

# Maximum token/character limit for serialized Graph-RAG context
MAX_CONTEXT_SIZE: int = 8000

# Reserved keywords / built-in functions across languages to exclude from internal repository call graphs
STDLIB_MODULES: set[str] = set(sys.builtin_module_names) | {
    # Python
    "os", "sys", "re", "math", "json", "ast", "typing", "collections",
    "functools", "itertools", "datetime", "time", "logging", "pathlib",
    "unittest", "pytest", "dataclasses", "abc", "enum", "copy", "traceback",
    "print", "len", "range", "str", "int", "float", "bool", "list", "dict", "set",
    # JS/TS
    "console", "log", "require", "import", "export", "return", "if", "else",
    "for", "while", "const", "let", "var", "function", "class", "async", "await",
    # Java/C++/Go
    "System", "out", "println", "main", "fmt", "Println", "Printf", "struct", "void"
}
