from __future__ import annotations

import os
from typing import Any

import httpx
from tenacity import Retrying, stop_after_attempt, wait_exponential

from arxiv_digest.config import AppConfig
from arxiv_digest.llm.base import LLMProvider, ProviderError
from arxiv_digest.llm.schemas import PaperAnalysis, validate_analysis_payload
from arxiv_digest.models import Paper
from arxiv_digest.prompts import build_analysis_messages
from arxiv_digest.utils import extract_json_object


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        config: AppConfig,
        provider_name: str,
        model: str,
        *,
        endpoint: str,
        api_key_env: str | None,
        profile_name: str | None = None,
        require_api_key: bool = True,
    ):
        super().__init__(config, provider_name, model, profile_name=profile_name)
        self.endpoint = endpoint.strip()
        self.api_key_env = api_key_env or ""
        if not self.endpoint:
            raise ProviderError(f"{provider_name} provider requires a non-empty HTTP endpoint.")
        if not self.model:
            raise ProviderError(f"{provider_name} provider requires a model name.")
        self.api_key = self._read_api_key(require_api_key)

    def analyze_paper(self, paper: Paper) -> PaperAnalysis:
        for attempt in Retrying(
            stop=stop_after_attempt(max(1, int(self.config.llm.max_retries))),
            wait=wait_exponential(multiplier=1, min=1, max=15),
            reraise=True,
        ):
            with attempt:
                return self._analyze_once(paper)
        raise RuntimeError("Unreachable retry state while calling LLM provider.")

    def _analyze_once(self, paper: Paper) -> PaperAnalysis:
        payload = {
            "model": self.model,
            "messages": build_analysis_messages(
                paper,
                profile_name=self.profile_name,
                profile=self.profile,
            ),
            "temperature": self.config.llm.temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        timeout = httpx.Timeout(self.config.llm.timeout_seconds)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(self.endpoint, json=payload, headers=headers)
            response.raise_for_status()
            response_json = response.json()
        content = self._extract_content(response_json)
        parsed = extract_json_object(content)
        return validate_analysis_payload(parsed, self.profile.topics)

    def _extract_content(self, response_json: dict[str, Any]) -> str:
        try:
            content = response_json["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"{self.name} response is not OpenAI-compatible: expected "
                "response['choices'][0]['message']['content']."
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError(f"{self.name} response content is empty.")
        return content

    def _read_api_key(self, require_api_key: bool) -> str | None:
        if not self.api_key_env:
            return None
        api_key = os.getenv(self.api_key_env)
        if require_api_key and not api_key:
            raise ProviderError(
                f"{self.name} provider requires API key environment variable "
                f"{self.api_key_env}, but it is not set."
            )
        return api_key


class CustomHTTPProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        config: AppConfig,
        provider_name: str,
        model: str,
        profile_name: str | None = None,
    ):
        provider_config = config.providers.custom_http
        super().__init__(
            config,
            provider_name,
            model or provider_config.model,
            endpoint=provider_config.endpoint,
            api_key_env=provider_config.api_key_env,
            profile_name=profile_name,
            require_api_key=True,
        )
