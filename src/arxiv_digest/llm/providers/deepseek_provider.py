from __future__ import annotations

from arxiv_digest.config import AppConfig
from arxiv_digest.llm.providers.custom_http_provider import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        config: AppConfig,
        provider_name: str,
        model: str,
        profile_name: str | None = None,
    ):
        provider_config = config.providers.deepseek
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
