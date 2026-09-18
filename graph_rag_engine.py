"""
Graph-RAG engine compatibility wrapper.
"""
from rag.serializer import serialize_ego_graph
from rag.prompt_builder import build_impact_prompts as build_llm_prompts

__all__ = ["serialize_ego_graph", "build_llm_prompts"]
