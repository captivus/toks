"""Registry tests — model lookup and provider inference."""

from __future__ import annotations

from count_tokens.registry import (
    get_registry,
    infer_provider,
    get_context_window,
    lookup_model,
    normalize_provider,
)


class TestRegistry:
    def test_get_registry_loads(self):
        registry = get_registry()
        assert isinstance(registry, dict)
        assert len(registry) > 100

    def test_infer_provider_claude(self):
        provider = infer_provider(model_id="claude-sonnet-4-6")
        assert provider == "claude"

    def test_infer_provider_openai(self):
        provider = infer_provider(model_id="gpt-4o-mini")
        assert provider == "openai"

    def test_infer_provider_gemini(self):
        provider = infer_provider(model_id="gemini-2.5-flash")
        assert provider == "gemini"

    def test_infer_provider_unknown(self):
        provider = infer_provider(model_id="nonexistent-model-xyz")
        assert provider is None

    def test_context_window(self):
        ctx = get_context_window(model_id="gpt-4o-mini")
        assert ctx is not None
        assert ctx > 0

    def test_normalize_provider(self):
        assert normalize_provider(litellm_provider="anthropic") == "claude"
        assert normalize_provider(litellm_provider="openai") == "openai"
        assert normalize_provider(litellm_provider="gemini") == "gemini"
        assert normalize_provider(litellm_provider="xai") == "grok"

    def test_lookup_model(self):
        entry = lookup_model(model_id="gpt-4o-mini")
        assert entry is not None
        assert "max_input_tokens" in entry
