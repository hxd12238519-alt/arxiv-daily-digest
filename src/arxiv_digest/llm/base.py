from __future__ import annotations

from abc import ABC, abstractmethod

from arxiv_digest.config import AppConfig
from arxiv_digest.llm.schemas import PaperAnalysis
from arxiv_digest.models import Paper


class ProviderError(RuntimeError):
    """Raised when an LLM provider cannot be configured or called."""


class LLMProvider(ABC):
    def __init__(
        self,
        config: AppConfig,
        provider_name: str,
        model: str,
        profile_name: str | None = None,
    ):
        self.config = config
        self.name = provider_name
        self.model = model
        self.profile_name, self.profile = config.get_profile(profile_name)

    @abstractmethod
    def analyze_paper(self, paper: Paper) -> PaperAnalysis:
        raise NotImplementedError


class ProviderFactory:
    @staticmethod
    def create(
        config: AppConfig,
        *,
        provider: str | None = None,
        model: str | None = None,
        profile_name: str | None = None,
    ) -> LLMProvider:
        provider_name = (provider or config.llm.provider).strip().lower()
        selected_model = _select_model(config, provider_name, model)

        if provider_name == "mock":
            from arxiv_digest.llm.providers.mock_provider import MockProvider

            return MockProvider(config, provider_name, selected_model, profile_name=profile_name)
        if provider_name == "custom_http":
            from arxiv_digest.llm.providers.custom_http_provider import CustomHTTPProvider

            return CustomHTTPProvider(
                config, provider_name, selected_model, profile_name=profile_name
            )
        if provider_name == "litellm":
            from arxiv_digest.llm.providers.litellm_provider import LiteLLMProvider

            return LiteLLMProvider(config, provider_name, selected_model, profile_name=profile_name)
        if provider_name == "gemini":
            from arxiv_digest.llm.providers.gemini_provider import GeminiProvider

            return GeminiProvider(config, provider_name, selected_model, profile_name=profile_name)
        if provider_name == "claude":
            from arxiv_digest.llm.providers.claude_provider import ClaudeProvider

            return ClaudeProvider(config, provider_name, selected_model, profile_name=profile_name)
        if provider_name == "deepseek":
            from arxiv_digest.llm.providers.deepseek_provider import DeepSeekProvider

            return DeepSeekProvider(
                config, provider_name, selected_model, profile_name=profile_name
            )
        if provider_name == "qwen":
            from arxiv_digest.llm.providers.qwen_provider import QwenProvider

            return QwenProvider(config, provider_name, selected_model, profile_name=profile_name)
        if provider_name == "ollama":
            from arxiv_digest.llm.providers.ollama_provider import OllamaProvider

            return OllamaProvider(config, provider_name, selected_model, profile_name=profile_name)

        supported = "mock, custom_http, litellm, gemini, claude, deepseek, qwen, ollama"
        raise ProviderError(
            f"Unknown LLM provider '{provider_name}'. Supported providers: {supported}."
        )


def _select_model(config: AppConfig, provider_name: str, model_override: str | None) -> str:
    if model_override:
        return model_override
    provider_config = getattr(config.providers, provider_name, None)
    provider_model = getattr(provider_config, "model", "") if provider_config else ""
    return provider_model or config.llm.model
