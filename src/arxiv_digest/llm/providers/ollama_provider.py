from __future__ import annotations

from typing import Any

import httpx
from tenacity import Retrying, stop_after_attempt, wait_exponential

from arxiv_digest.config import AppConfig
from arxiv_digest.llm.base import LLMProvider, ProviderError
from arxiv_digest.llm.schemas import PaperAnalysis, validate_analysis_payload
from arxiv_digest.models import Paper
from arxiv_digest.prompts import build_analysis_messages
from arxiv_digest.utils import extract_json_object


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        config: AppConfig,
        provider_name: str,
        model: str,
        profile_name: str | None = None,
    ):
        provider_config = config.providers.ollama
        selected_model = model or provider_config.model
        if not selected_model:
            raise ProviderError("ollama provider requires providers.ollama.model.")
        super().__init__(config, provider_name, selected_model, profile_name=profile_name)
        self.base_url = provider_config.base_url.rstrip("/")
        if not self.base_url:
            raise ProviderError("ollama provider requires providers.ollama.base_url.")

    def analyze_paper(self, paper: Paper) -> PaperAnalysis:
        for attempt in Retrying(
            stop=stop_after_attempt(max(1, int(self.config.llm.max_retries))),
            wait=wait_exponential(multiplier=1, min=1, max=15),
            reraise=True,
        ):
            with attempt:
                return self._analyze_once(paper)
        raise RuntimeError("Unreachable retry state while calling Ollama.")

    def _analyze_once(self, paper: Paper) -> PaperAnalysis:
        payload = {
            "model": self.model,
            "messages": build_analysis_messages(
                paper,
                profile_name=self.profile_name,
                profile=self.profile,
            ),
            "stream": False,
            "format": "json",
            "options": {"temperature": self.config.llm.temperature},
        }
        timeout = httpx.Timeout(self.config.llm.timeout_seconds)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            response_json = response.json()
        content = self._extract_content(response_json)
        parsed = extract_json_object(content)
        return validate_analysis_payload(parsed, self.profile.topics)

    def _extract_content(self, response_json: dict[str, Any]) -> str:
        message = response_json.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
        if isinstance(response_json.get("response"), str):
            return response_json["response"]
        raise ProviderError("ollama response must contain message.content or response.")
