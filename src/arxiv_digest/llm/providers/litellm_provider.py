from __future__ import annotations

from arxiv_digest.config import AppConfig
from arxiv_digest.llm.base import ProviderError
from arxiv_digest.llm.providers.custom_http_provider import OpenAICompatibleProvider


class LiteLLMProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        config: AppConfig,
        provider_name: str,
        model: str,
        profile_name: str | None = None,
    ):
        provider_config = config.providers.litellm
        if not provider_config.base_url:
            raise ProviderError(
                "litellm provider requires providers.litellm.base_url, for example "
                "http://localhost:4000/v1 when using a LiteLLM proxy."
            )
        endpoint = f"{provider_config.base_url.rstrip('/')}/chat/completions"
        super().__init__(
            config,
            provider_name,
            model or provider_config.model,
            endpoint=endpoint,
            api_key_env=provider_config.api_key_env,
            profile_name=profile_name,
            require_api_key=True,
        )
