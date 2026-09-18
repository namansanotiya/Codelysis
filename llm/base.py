"""
Base LLM Client interface.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from core.models import ImpactSummary


class BaseLLMClient(ABC):
    @abstractmethod
    def generate_report(
        self,
        graph_context: str,
        diff_text: str,
        impact_summary: Optional[ImpactSummary] = None
    ) -> str:
        """Generate markdown impact analysis report."""
        pass
