"""
Prompt Builder Module for RepoGraph Impact Analysis & Co-Change Recommendations.
"""
from typing import Dict


def build_impact_prompts(graph_context: str, diff_text: str) -> Dict[str, str]:
    """
    Construct System and User Prompts for LLM Code Change Impact Analysis.
    """
    system_prompt = (
        "You are an expert Software Architect and Code Change Impact Analyzer.\n"
        "Your task is to analyze a code modification (Git diff) alongside its extracted repository dependency graph (Graph-RAG context).\n"
        "Identify all downstream files, symbols, function callers, class implementations, and test cases affected by the change.\n"
        "Provide structured recommendations detailing affected files, line numbers, reason for impact, required changes, and confidence score."
    )

    user_prompt = f"""
Analyze the following Git diff and repository dependency graph context to determine all affected code components.

{graph_context}

Provide a structured Markdown report answering:
1. **Summary of Change**: What functions/methods/signatures/logic were changed?
2. **Affected Files & Line Numbers**: Which files and specific lines are impacted?
3. **Impact Rationale**: Why is each file impacted (e.g. direct caller, indirect caller, changed signature, test case)?
4. **Recommended Co-Changes**: What specific updates/refactors are needed in each affected file?
5. **Testing Requirements**: Which test files need updating or new test cases added?

Format the output clearly in GitHub-flavored Markdown.
"""
    return {
        "system_prompt": system_prompt.strip(),
        "user_prompt": user_prompt.strip()
    }
