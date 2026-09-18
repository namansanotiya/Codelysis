"""
Unit tests for GeminiClient and MockLLMClient.
"""
import unittest
from unittest.mock import patch, MagicMock

from core.models import ImpactSummary
from llm.mock_client import MockLLMClient
from llm.gemini_client import GeminiClient


class TestLLMClients(unittest.TestCase):

    def setUp(self):
        self.summary = ImpactSummary(
            seed_nodes=[{"file": "auth/service.py", "line": 3, "name": "validate_token", "category": "function", "snippet": "def validate_token():"}],
            direct_callers=[{"file": "core/service.py", "line": 6, "name": "process_request", "category": "method"}],
            indirect_callers=[{"file": "tests/test_auth.py", "line": 5, "name": "test_validate", "category": "function"}],
            callees=[],
            affected_files=["core/service.py", "tests/test_auth.py"],
            total_ego_nodes=5,
            total_ego_edges=4
        )

    def test_mock_llm_client(self):
        mock_client = MockLLMClient()
        report = mock_client.generate_report(
            graph_context="Test Context",
            diff_text="diff --git a/auth/service.py",
            impact_summary=self.summary
        )

        self.assertIn("Code Change Impact Analysis", report)
        self.assertIn("auth/service.py", report)
        self.assertIn("core/service.py", report)
        self.assertIn("tests/test_auth.py", report)
        self.assertIn("Direct Invocation Site (1-hop)", report)

    def test_gemini_client_offline_fallback(self):
        client = GeminiClient(api_key=None)  # No key
        report = client.generate_report(
            graph_context="Test Context",
            diff_text="diff --git a/auth/service.py",
            impact_summary=self.summary
        )
        self.assertIn("Code Change Impact Analysis", report)
        self.assertIn("core/service.py", report)

    @patch("requests.post")
    def test_gemini_client_rest_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "### Gemini Impact Report\nAffected: core/service.py"}]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        # Patch genai so it simulates SDK unavailability and tests REST
        with patch.dict("sys.modules", {"google.genai": None, "google": None}):
            client = GeminiClient(api_key="mock_key")
            report = client.generate_report(
                graph_context="Test Context",
                diff_text="diff text",
                impact_summary=self.summary
            )
            self.assertIn("Gemini Impact Report", report)


if __name__ == "__main__":
    unittest.main()
