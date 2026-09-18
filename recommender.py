"""
Recommender compatibility wrapper.
"""
from typing import Optional, Dict, Any
from core.models import ImpactSummary
from llm.gemini_client import GeminiClient
from llm.mock_client import MockLLMClient


def generate_recommendations(
    graph_context: str,
    diff_text: str,
    impact_summary: Optional[Any] = None,
    api_key: Optional[str] = None
) -> str:
    # Convert dict to ImpactSummary if needed
    summary_obj = None
    if isinstance(impact_summary, ImpactSummary):
        summary_obj = impact_summary
    elif isinstance(impact_summary, dict):
        summary_obj = ImpactSummary(
            seed_nodes=impact_summary.get("seed_nodes", []),
            direct_callers=impact_summary.get("direct_callers", []),
            indirect_callers=impact_summary.get("indirect_callers", []),
            callees=impact_summary.get("callees", []),
            affected_files=impact_summary.get("affected_files", []),
            total_ego_nodes=impact_summary.get("total_ego_nodes", 0),
            total_ego_edges=impact_summary.get("total_ego_edges", 0)
        )

    client = GeminiClient(api_key=api_key)
    return client.generate_report(graph_context, diff_text, summary_obj)


def generate_mock_recommendation_report(
    graph_context: str,
    diff_text: str,
    impact_summary: Optional[Any] = None
) -> str:
    mock = MockLLMClient()
    return mock.generate_report(graph_context, diff_text, impact_summary)


__all__ = ["generate_recommendations", "generate_mock_recommendation_report"]
