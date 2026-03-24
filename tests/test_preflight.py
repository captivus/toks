"""Preflight validation tests.

Root cause test: validates that every provider + model combination
actually works with the provider's API before we try to count real files.
This catches:
- Invalid/deprecated model names
- Models not supported by the countTokens endpoint
- API key issues
- Provider endpoint changes
- Payload format problems

If this test fails, ALL file counting for that provider will fail.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from count_tokens.providers.claude import ClaudeProvider
from count_tokens.providers.openai import OpenAIProvider
from count_tokens.providers.gemini import GeminiProvider
from count_tokens.providers.grok import GrokProvider

# The test payload — minimal content that every provider must accept
PREFLIGHT_CONTENT = b"hello"
PREFLIGHT_MIME = "text/plain"


def _preflight(provider, model):
    """Send a minimal token count request and verify it succeeds."""
    result = asyncio.run(provider.count_tokens(
        content=PREFLIGHT_CONTENT,
        mime_type=PREFLIGHT_MIME,
        model=model,
    ))
    assert result.total_tokens > 0, f"Preflight for {provider.provider_name}/{model} returned 0 tokens"
    return result


@pytest.mark.claude
class TestClaudePreflight:
    """Validate all Claude models we might use."""

    def test_sonnet(self):
        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        _preflight(provider, "claude-sonnet-4-6")

    def test_haiku(self):
        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        _preflight(provider, "claude-haiku-4-5-20251001")


@pytest.mark.openai
class TestOpenAIPreflight:
    """Validate all OpenAI models we might use."""

    def test_gpt4o_mini(self):
        provider = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"])
        _preflight(provider, "gpt-4o-mini")


@pytest.mark.gemini
class TestGeminiPreflight:
    """Validate all Gemini models we might use."""

    def test_gemini_2_5_flash(self):
        provider = GeminiProvider(api_key=os.environ["GEMINI_API_KEY"])
        _preflight(provider, "gemini-2.5-flash")

    def test_gemini_2_5_pro(self):
        provider = GeminiProvider(api_key=os.environ["GEMINI_API_KEY"])
        _preflight(provider, "gemini-2.5-pro")


@pytest.mark.grok
class TestGrokPreflight:
    """Validate all Grok models we might use."""

    def test_grok_3(self):
        provider = GrokProvider(api_key=os.environ["GROK_API_KEY"])
        _preflight(provider, "grok-3")


class TestConfiguredModelsPreflight:
    """Validate that the models configured in the user's config.toml actually work.

    This is the most important test — it catches exactly the failure mode
    where a user configures a model name during setup that the API doesn't accept.
    """

    def test_all_configured_providers(self):
        from count_tokens.config import load_config, load_env_api_key
        from count_tokens.providers import get_provider

        config = load_config()
        if config is None:
            pytest.skip("No config file found")

        failures = []
        for name, pc in config.providers.items():
            api_key = load_env_api_key(provider=name)
            if not api_key:
                failures.append(f"{name}: no API key configured")
                continue

            provider = get_provider(name=name, api_key=api_key)

            # Test the API model
            try:
                result = asyncio.run(provider.count_tokens(
                    content=PREFLIGHT_CONTENT, mime_type=PREFLIGHT_MIME, model=pc.model,
                ))
                assert result.total_tokens > 0
            except Exception as exc:
                failures.append(f"{name}/{pc.model} (API model): {exc}")

            # Test the agent model if configured
            if pc.agent_model:
                try:
                    result = asyncio.run(provider.count_tokens(
                        content=PREFLIGHT_CONTENT, mime_type=PREFLIGHT_MIME, model=pc.agent_model,
                    ))
                    assert result.total_tokens > 0
                except Exception as exc:
                    failures.append(f"{name}/{pc.agent_model} (agent model): {exc}")

        if failures:
            pytest.fail("Preflight failures for configured models:\n" + "\n".join(f"  - {f}" for f in failures))
