"""
Google Gemini API Client.
Interfaces with Gemini API for LLM-powered Code Change Impact Analysis.
Falls back to MockLLMClient if API key is not configured or network call fails.
"""
import os
import logging
from typing import Optional
import requests

from core.models import ImpactSummary
from rag.prompt_builder import build_impact_prompts
from llm.base import BaseLLMClient
from llm.mock_client import MockLLMClient

logger = logging.getLogger("gemini_client")


class GeminiClient(BaseLLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        timeout: int = 30
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        self.timeout = timeout
        self.fallback_client = MockLLMClient()

    def generate_report(
        self,
        graph_context: str,
        diff_text: str,
        impact_summary: Optional[ImpactSummary] = None
    ) -> str:
        if not self.api_key:
            logger.info("No Gemini API key detected (GEMINI_API_KEY / GOOGLE_API_KEY). Using Rule-Based Analyzer...")
            return self.fallback_client.generate_report(graph_context, diff_text, impact_summary)

        prompts = build_impact_prompts(graph_context, diff_text)
        system_text = prompts["system_prompt"]
        user_text = prompts["user_prompt"]

        # 1. Try google-genai SDK if available
        try:
            from google import genai
            logger.info(f"Querying Gemini API via SDK ({self.model_name})...")
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model_name,
                contents=f"{system_text}\n\n{user_text}"
            )
            if response and response.text:
                return response.text.strip()
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Google GenAI SDK call failed: {e}. Trying REST endpoint...")

        # 2. Direct REST API Call
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": system_text}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_text}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096
            }
        }

        try:
            logger.info(f"Querying Gemini REST endpoint ({self.model_name})...")
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
            else:
                logger.warning(f"Gemini API returned error HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Gemini REST request failed: {e}")

        logger.info("Falling back to Rule-Based Recommender...")
        return self.fallback_client.generate_report(graph_context, diff_text, impact_summary)
