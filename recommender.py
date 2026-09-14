"""
LLM Recommender Engine module.
Sends Graph-RAG context & Git diff to an LLM (Gemini or OpenAI) to generate structured co-change impact recommendations.
Includes a fallback rule-based analyzer for offline / keyless execution.
"""
import os
import logging
from typing import Dict, Any, Optional

from code_impact_graph_rag.config import LLM_MODEL
from code_impact_graph_rag.graph_rag_engine import build_llm_prompts

logger = logging.getLogger("recommender")


def generate_recommendations(
    graph_context: str,
    diff_text: str,
    impact_summary: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None
) -> str:
    """
    Generate structured code change impact recommendations report.
    Uses Google GenAI (Gemini) or OpenAI if API keys are available, otherwise uses Mock Recommender.
    """
    prompts = build_llm_prompts(graph_context, diff_text)
    system_prompt = prompts["system_prompt"]
    user_prompt = prompts["user_prompt"]

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

    # 2. Try OpenAI API
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            import openai
            logger.info("Querying OpenAI API (gpt-4o)...")
            client = openai.OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"OpenAI API query failed: {e}. Falling back to mock recommender.")

    # 3. Fallback Mock Recommender (Deterministic Rule-Based Generator)
    logger.info("Using Rule-Based Graph-RAG Recommender Engine...")
    return generate_mock_recommendation_report(graph_context, diff_text, impact_summary)


def generate_mock_recommendation_report(
    graph_context: str,
    diff_text: str,
    impact_summary: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generates a high-quality Markdown impact report when LLM API is unavailable.
    """
    report: list[str] = []
    report.append("# Code Change Impact Analysis & Co-Change Recommendation Report")
    report.append("")
    report.append("> [!NOTE]")
    report.append("> Analysis generated using Graph-RAG k-hop Ego Subgraph Traversal.")
    report.append("")

    report.append("## 1. Executive Summary")
    report.append("The analyzed Git diff modifies core repository logic. The k-hop dependency graph traversal identified downstream caller sites, dependent services, and unit test suites that are affected and require co-changes.")
    report.append("")

    report.append("## 2. Seed Code Modifications")
    if impact_summary and impact_summary.get("seed_nodes"):
        for seed in impact_summary["seed_nodes"]:
            file = seed.get("file", "unknown")
            line = seed.get("line", 0)
            name = seed.get("name", "unknown")
            category = seed.get("category", "symbol")
            snippet = seed.get("snippet", "")
            report.append(f"- **File:** `{file}`")
            report.append(f"  - **Symbol:** `{name}` ({category.capitalize()}) at line {line}")
            if snippet:
                report.append(f"  - **Snippet:** `{snippet}`")
    else:
        report.append("- Modified files detected in Git diff.")
    report.append("")

    report.append("## 3. Downstream Affected Components & Co-Change Recommendations")

    if impact_summary:
        direct_callers = impact_summary.get("direct_callers", [])
        indirect_callers = impact_summary.get("indirect_callers", [])
        affected_files = impact_summary.get("affected_files", [])

        idx = 1
        # Direct Callers
        for caller in direct_callers:
            file = caller.get("file", "")
            line = caller.get("line", 0)
            name = caller.get("name", "")
            cat = caller.get("category", "symbol")
            report.append(f"### {idx}. `{file}`")
            report.append(f"- **Line:** {line}")
            report.append(f"- **Affected Symbol:** `{name}` ({cat})")
            report.append("- **Impact Category:** Direct Invocation Site (1-hop)")
            report.append("- **Reason:** Directly calls modified seed function/symbol whose behavior or signature changed.")
            report.append(f"- **Recommended Action:** Review call arguments in `{name}` at line {line} to align with new parameters and handle updated return types.")
            report.append("- **Confidence:** High")
            report.append("")
            idx += 1

        # Indirect / Test Callers
        for caller in indirect_callers:
            file = caller.get("file", "")
            line = caller.get("line", 0)
            name = caller.get("name", "")
            cat = caller.get("category", "symbol")
            is_test = "test" in file.lower()
            report.append(f"### {idx}. `{file}`")
            report.append(f"- **Line:** {line}")
            report.append(f"- **Affected Symbol:** `{name}` ({cat})")
            report.append(f"- **Impact Category:** {'Test Suite / Mocking' if is_test else 'Indirect Downstream Caller (2-hop)'}")
            report.append(f"- **Reason:** {'Contains test cases or mocks validating the changed code path.' if is_test else 'Depends on upstream component affected by the modification.'}")
            report.append(f"- **Recommended Action:** {'Update test assertions and mock return values to match updated logic.' if is_test else 'Re-verify workflow integration and execute test suite.'}")
            report.append(f"- **Confidence:** {'High' if is_test else 'Medium'}")
            report.append("")
            idx += 1

        if idx == 1:
            report.append("No downstream external caller files were directly affected within the k-hop subgraph.")
            report.append("")

    report.append("## 4. Verification & Testing Checklist")
    report.append("- [ ] Verify signature compatibility across all call sites.")
    report.append("- [ ] Run unit test suite for modified module and callers.")
    report.append("- [ ] Execute integration tests across affected components.")

    return "\n".join(report)
