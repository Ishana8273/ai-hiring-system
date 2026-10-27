"""
Groq API wrapper for LLM inference.
Centralized client with retry logic, error handling, and JSON parsing.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper around Groq Llama 3.3 70B via LangChain."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
    ):
        """Initialize the LLM client with Groq API credentials."""
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found. Set it in .env")

        self.model_name = model_name or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        self.temperature = (
            temperature
            if temperature is not None
            else float(os.getenv("LLM_TEMPERATURE", "0.3"))
        )
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "4096"))
        self.max_retries = max_retries

        self.llm = ChatGroq(
            api_key=self.api_key,
            model_name=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        logger.info("LLMClient initialized: model=%s", self.model_name)

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompt to LLM, return raw text. Retries with exponential backoff."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("LLM invoke attempt %d/%d", attempt, self.max_retries)
                response = self.llm.invoke(messages)
                return response.content
            except Exception as e:
                last_exc = e
                logger.warning("LLM attempt %d failed: %s", attempt, e)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        logger.error("All %d LLM attempts failed", self.max_retries)
        raise last_exc  # type: ignore[misc]

    def invoke_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Send prompt and parse JSON response with retries."""
        for attempt in range(1, self.max_retries + 1):
            try:
                raw = self.invoke(system_prompt, user_prompt)
                return self._extract_json(raw)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("JSON parse attempt %d failed: %s", attempt, e)
                user_prompt += (
                    "\n\nIMPORTANT: Respond with valid JSON only. "
                    "No markdown, no explanation, just the JSON object."
                )
        raise ValueError("Failed to parse JSON after retries")

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract JSON from LLM response handling markdown blocks."""
        cleaned = text.strip()

        # Try direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try markdown code blocks
        for marker in ["```json", "```"]:
            if marker in cleaned:
                start = cleaned.find(marker) + len(marker)
                end = cleaned.find("```", start)
                if end != -1:
                    try:
                        return json.loads(cleaned[start:end].strip())
                    except json.JSONDecodeError:
                        pass

        # Try brace matching
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"No JSON found in: {cleaned[:200]}")


_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create module-level LLMClient singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client