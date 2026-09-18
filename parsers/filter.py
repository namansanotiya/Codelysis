"""
Relation Filtering Module (RepoGraph ICLR 2025, Section 3.1 Step 2).
Excludes repository-independent relations:
1. Global relations: standard library and language built-ins.
2. Local relations: third-party imported functions/classes.
"""
import re
from typing import Set, Dict

# Multi-language built-ins and standard keywords
GLOBAL_BUILTINS: Dict[str, Set[str]] = {
    "python": {
        "print", "len", "range", "str", "int", "float", "bool", "list", "dict", "set",
        "tuple", "enumerate", "zip", "map", "filter", "min", "max", "sum", "abs",
        "open", "isinstance", "issubclass", "getattr", "setattr", "hasattr", "delattr",
        "super", "type", "id", "hash", "repr", "iter", "next", "any", "all",
        "if", "else", "elif", "for", "while", "return", "def", "class", "import", "from",
        "as", "try", "except", "finally", "raise", "with", "yield", "async", "await",
        "os", "sys", "re", "math", "json", "time", "datetime", "logging"
    },
    "javascript": {
        "console", "log", "warn", "error", "info", "require", "import", "export", "default",
        "return", "if", "else", "for", "while", "const", "let", "var", "function", "class",
        "async", "await", "new", "this", "super", "try", "catch", "finally", "throw",
        "document", "window", "Promise", "setTimeout", "setInterval", "clearTimeout",
        "Array", "Object", "String", "Number", "Boolean", "JSON", "Math", "Date"
    },
    "java": {
        "System", "out", "println", "print", "main", "String", "Integer", "Double", "Boolean",
        "List", "Map", "Set", "ArrayList", "HashMap", "HashSet", "Arrays", "Collections",
        "Math", "public", "private", "protected", "static", "final", "void", "class",
        "interface", "new", "return", "if", "else", "for", "while", "try", "catch", "throw"
    },
    "cpp": {
        "printf", "scanf", "cout", "cin", "endl", "std", "string", "vector", "map", "set",
        "malloc", "free", "sizeof", "new", "delete", "nullptr", "NULL", "void", "int", "char",
        "class", "struct", "template", "namespace", "using", "include", "return", "if", "else"
    },
    "golang": {
        "fmt", "Println", "Printf", "Print", "Sprintf", "make", "new", "len", "cap",
        "append", "copy", "panic", "recover", "close", "func", "type", "struct", "interface",
        "package", "import", "return", "if", "else", "for", "range", "go", "select", "chan"
    },
    "rust": {
        "println", "print", "format", "vec", "panic", "Some", "None", "Ok", "Err",
        "String", "Vec", "Option", "Result", "fn", "struct", "enum", "impl", "trait",
        "pub", "mut", "let", "use", "mod", "return", "match", "if", "else", "for", "while"
    },
    "csharp": {
        "Console", "WriteLine", "Write", "string", "int", "var", "public", "private", "protected",
        "static", "void", "class", "interface", "namespace", "using", "return", "new", "if", "else"
    }
}

# Aggregate set of universal keywords across all languages
UNIVERSAL_BUILTINS: Set[str] = set()
for lang_builtins in GLOBAL_BUILTINS.values():
    UNIVERSAL_BUILTINS.update(lang_builtins)


def is_builtin_or_stdlib(symbol: str, language: str = None) -> bool:
    """
    Check whether a symbol belongs to standard library / built-in keywords.
    """
    if not symbol:
        return True
    
    if language and language.lower() in GLOBAL_BUILTINS:
        if symbol in GLOBAL_BUILTINS[language.lower()]:
            return True

    return symbol in UNIVERSAL_BUILTINS


def extract_third_party_imports(content: str) -> Set[str]:
    """
    Extract imported module / function names to filter out external library calls.
    Supports Python, JS/TS, Java, Go, Rust, C++.
    """
    third_party_names: Set[str] = set()
    
    # Python: import foo, from foo import bar
    for match in re.finditer(r"^\s*(?:from\s+[\w\.]+\s+import\s+([\w,\s]+)|import\s+([\w,\s\.]+))", content, re.MULTILINE):
        for grp in match.groups():
            if grp:
                for item in grp.split(","):
                    name = item.strip().split(" as ")[0].strip()
                    if name:
                        third_party_names.add(name)

    # JS/TS: import { foo } from 'bar'; (skip if relative import starting with .)
    for match in re.finditer(r"import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]", content):
        from_module = match.group(3).strip()
        if from_module.startswith("."):
            continue  # Local project import
        if match.group(1):
            for item in match.group(1).split(","):
                name = item.strip().split(" as ")[0].strip()
                if name:
                    third_party_names.add(name)
        elif match.group(2):
            third_party_names.add(match.group(2).strip())

    return third_party_names
