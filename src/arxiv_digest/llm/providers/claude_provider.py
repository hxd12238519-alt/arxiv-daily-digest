from __future__ import annotations

import os

from arxiv_digest.config import AppConfig
from arxiv_digest.llm.base import LLMProvider, ProviderError
from arxiv_digest.llm.schemas import PaperAnalysis
from arxiv_digest.models import Paper


class ClaudeProvider(LLMProvider):
    def __init__(
        self,
        config: AppConfig,
        provider_name: str,
        model: str,
        profile_name: str | None = None,
    ):
        provider_config = config.providers.claude
        selected_model = model or provider_config.model
        if not selected_model:
            raise ProviderError("claude provider requires providers.claude.model or llm.model.")
        if not os.getenv(provider_config.api_key_env):
            raise ProviderError(
                f"claude provider requires API key environment variable "
                f"{provider_config.api_key_env}, but it is not set."
            )
        super().__init__(config, provider_name, selected_model, profile_name=profile_name)

    def analyze_paper(self, paper: Paper) -> PaperAnalysis:
        raise ProviderError(
            "claude provider is declared but not implemented in this core package. "
            "Use custom_http with an Anthropic-compatible gateway, or add an "
            "Anthropic SDK integration."
        )
