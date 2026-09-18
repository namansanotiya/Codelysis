"""
RAG package for RepoGraph context serialization and prompt synthesis.
"""
from rag.serializer import serialize_ego_graph
from rag.prompt_builder import build_impact_prompts

__all__ = [
    "serialize_ego_graph",
    "build_impact_prompts",
]
