"""Provider registry and lookup."""

from toks.providers.base import (
    TokenCountProvider,
    TokenCountResult,
    UnsupportedFileTypeError,
)
from toks.providers.claude import ClaudeProvider
from toks.providers.openai import OpenAIProvider
from toks.providers.gemini import GeminiProvider
from toks.providers.grok import GrokProvider

PROVIDERS: dict[str, type[TokenCountProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "grok": GrokProvider,
}

PROVIDER_ENV_KEYS: dict[str, str] = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "grok": "GROK_API_KEY",
}


def get_provider(*, name: str, api_key: str) -> TokenCountProvider:
    provider_class = PROVIDERS.get(name)
    if provider_class is None:
        raise ValueError(f"Unknown provider: {name}. Valid providers: {', '.join(PROVIDERS)}")
    return provider_class(api_key=api_key)
