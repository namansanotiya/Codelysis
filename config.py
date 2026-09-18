"""
Configuration settings for Codelysis (RepoGraph ICLR 2025).
Supports Multi-Language Repositories (Python, JS/TS, Java, C/C++, Go, Rust, C#).
"""
import os

# Number of graph hops for ego-subgraph extraction (RepoGraph Section 3.2, default k=2)
K_HOPS: int = 2

# Supported file extensions across programming languages
SUPPORTED_EXTENSIONS: list[str] = [
    ".py",                          # Python
    ".js", ".jsx", ".ts", ".tsx",   # JavaScript / TypeScript
    ".mjs", ".cjs",
    ".java", ".kt",                 # Java / Kotlin
    ".c", ".cpp", ".cc", ".cxx",    # C / C++
    ".h", ".hpp",
    ".go",                          # Go
    ".rs",                          # Rust
    ".cs",                          # C#
]

# Default Gemini model choice
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")

# Maximum token/character limit for serialized Graph-RAG context (RepoGraph Table 4)
MAX_CONTEXT_SIZE: int = 8000

# Default sample unified diff for testing
DEFAULT_SAMPLE_DIFF: str = """--- a/auth/service.py
+++ b/auth/service.py
@@ -3,4 +3,4 @@
-def validate_token(token: str) -> bool:
+def validate_token(token: str, require_admin: bool = False, tenant_id: str = "default") -> bool:
     \"\"\"Validates security token and checks authorization level.\"\"\"
     claims = decode_token(token)
"""
