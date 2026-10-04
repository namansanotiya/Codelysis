"""
LLM Recommender Engine module.
Sends Graph-RAG context & Git diff to an LLM (Gemini or OpenAI) to generate structured co-change impact recommendations.
Includes a fallback rule-based analyzer for offline / keyless execution with compact file summary options.
"""
import os
import logging
from typing import Dict, Any, Optional, List

from code_impact_graph_rag.config import LLM_MODEL
from code_impact_graph_rag.graph_rag_engine import build_llm_prompts

logger = logging.getLogger("recommender")


def generate_recommendations(
    graph_context: str,
    diff_text: str,
    impact_summary: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    compact: bool = True
) -> str:
    """
    Generate structured code change impact recommendations report.
    Uses Google GenAI (Gemini) or OpenAI if API keys are available, otherwise uses Mock Recommender.
    `compact=True` produces a clean, concise file-level summary highlighting only affected files and lines.
    """
    prompts = build_llm_prompts(graph_context, diff_text)
    system_prompt = prompts["system_prompt"]
    user_prompt = prompts["user_prompt"]

    if compact:
        system_prompt += "\nFormat the response concisely. Group affected components by FILE and list specific line numbers and required actions in short bullet points."

    # 1. Try Gemini API
    gemini_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        try:
            from google import genai
            logger.info(f"Querying Gemini API model ({LLM_MODEL})...")
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=f"{system_prompt}\n\n{user_prompt}"
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini API query failed: {e}. Falling back to mock recommender.")

    # # 2. Try OpenAI API
    # openai_key = os.getenv("OPENAI_API_KEY")
    # if openai_key:
    #     try:
    #         import openai
    #         logger.info("Querying OpenAI API (gpt-4o)...")
    #         client = openai.OpenAI(api_key=openai_key)
    #         response = client.chat.completions.create(
    #             model="gpt-4o",
    #             messages=[
    #                 {"role": "system", "content": system_prompt},
    #                 {"role": "user", "content": user_prompt}
    #             ]
    #         )
    #         if response.choices and response.choices[0].message.content:
    #             return response.choices[0].message.content.strip()
    #     except Exception as e:
    #         logger.warning(f"OpenAI API query failed: {e}. Falling back to mock recommender.")

    # 3. Fallback Mock Recommender (Compact Generator)
    logger.info("Using Rule-Based Graph-RAG Recommender Engine...")
    return generate_compact_recommendation_report(graph_context, diff_text, impact_summary)


def generate_compact_recommendation_report(
    graph_context: str,
    diff_text: str,
    impact_summary: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generates a clean, compact Markdown report grouping affected caller sites by FILE.
    """
    report: List[str] = []
    report.append("# Code Change Impact Analysis — Affected Files Summary")
    report.append("")

    if not impact_summary:
        report.append("No impact summary available.")
        return "\n".join(report)

    seed_nodes = impact_summary.get("seed_nodes", [])
    direct_callers = impact_summary.get("direct_callers", [])
    indirect_callers = impact_summary.get("indirect_callers", [])

    # 1. Seed Changes (Filter to definition sites and limit display per file)
    report.append("### 1. Modified Seed Files")
    seed_files_map: Dict[str, List[str]] = {}
    for seed in seed_nodes:
        # Prioritize definition nodes or symbols
        if seed.get("type") == "def" or seed.get("category") in ("function", "method", "class"):
            f = seed.get("file", "unknown")
            name = seed.get("name", "")
            line = seed.get("line", 0)
            entry = f"`{name}` (Line {line})"
            if entry not in seed_files_map.setdefault(f, []):
                seed_files_map[f].append(entry)

    if not seed_files_map:
        for seed in seed_nodes:
            f = seed.get("file", "unknown")
            name = seed.get("name", "")
            line = seed.get("line", 0)
            entry = f"`{name}` (Line {line})"
            if entry not in seed_files_map.setdefault(f, []):
                seed_files_map[f].append(entry)

    for f, symbols in seed_files_map.items():
        disp_symbols = symbols[:3]
        extra = f" (+{len(symbols)-3} more)" if len(symbols) > 3 else ""
        report.append(f"- **{f}**: {', '.join(disp_symbols)}{extra}")
    report.append("")

    # 2. Group Direct & Indirect Callers by File
    file_impacts: Dict[str, Dict[str, Any]] = {}

    for caller in direct_callers:
        f = caller.get("file", "")
        if not f:
            continue
        if f not in file_impacts:
            file_impacts[f] = {"direct": [], "indirect": [], "test": False}
        file_impacts[f]["direct"].append(caller)

    for caller in indirect_callers:
        f = caller.get("file", "")
        if not f:
            continue
        if f not in file_impacts:
            file_impacts[f] = {"direct": [], "indirect": [], "test": "test" in f.lower()}
        file_impacts[f]["indirect"].append(caller)
        if "test" in f.lower():
            file_impacts[f]["test"] = True

    report.append(f"### 2. Files Requiring Co-Changes ({len(file_impacts)} Files Impacted)")
    report.append("")

    if not file_impacts:
        report.append("No downstream external files require changes.")
        return "\n".join(report)

    # Sort files: files with direct callers first
    sorted_files = sorted(file_impacts.keys(), key=lambda x: (len(file_impacts[x]["direct"]) == 0, x))

    for f in sorted_files:
        info = file_impacts[f]
        direct_list = info["direct"]
        indirect_list = info["indirect"]
        is_test = info["test"]

        impact_type = "High (Direct Invocation)" if direct_list else ("Test Suite" if is_test else "Medium (2-hop Dependency)")
        lines = sorted(list({c.get("line") for c in direct_list + indirect_list if c.get("line")}))
        symbols = sorted(list({c.get("name") for c in direct_list + indirect_list if c.get("name")}))

        lines_str = ", ".join(f"Line {l}" for l in lines[:6])
        if len(lines) > 6:
            lines_str += f" (+{len(lines)-6} more)"
        symbols_str = ", ".join(f"`{s}`" for s in symbols[:3])
        if len(symbols) > 3:
            symbols_str += f" (+{len(symbols)-3} more)"

        report.append(f"#### 📁 `{f}`")
        report.append(f"- **Impact Level:** {impact_type}")
        report.append(f"- **Affected Lines:** {lines_str}")
        report.append(f"- **Affected Symbols:** {symbols_str}")
        if direct_list:
            report.append("- **Action Required:** Update call arguments to match modified function signature.")
        elif is_test:
            report.append("- **Action Required:** Update unit test assertions and mocks.")
        else:
            report.append("- **Action Required:** Re-verify workflow integration & execute tests.")
        report.append("")

    report.append("### 3. Quick Checklist")
    report.append("- [ ] Update direct caller sites in high-priority files.")
    report.append("- [ ] Run unit and integration test suites.")

    return "\n".join(report)
