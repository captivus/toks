"""Registry tests — model lookup and provider inference."""

from __future__ import annotations

from toks.registry import (
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
        provider = infer_provider(model_id="claude-sonnet-5-5")
        assert provider == "claude"

    def test_infer_provider_openai(self):
        provider = infer_provider(model_id="gpt-6.1-sol")
        assert provider == "openai"

    def test_infer_provider_gemini(self):
        provider = infer_provider(model_id="gemini-3.8-flash")
        assert provider == "gemini"

    def test_infer_provider_grok(self):
        provider = infer_provider(model_id="grok-4.7")
        assert provider == "grok"

    def test_lookup_prefers_native_provider_entry(self):
        registry = {
            "azure_ai/grok-9": {"litellm_provider": "azure_ai", "max_input_tokens": 1},
            "vertex_ai/xai/grok-9": {"litellm_provider": "vertex_ai", "max_input_tokens": 2},
            "xai/grok-9": {"litellm_provider": "xai", "max_input_tokens": 3},
        }
        assert infer_provider(model_id="grok-9", registry=registry) == "grok"
        assert get_context_window(model_id="grok-9", registry=registry) == 3

    def test_infer_provider_unknown(self):
        provider = infer_provider(model_id="nonexistent-model-xyz")
        assert provider is None

    def test_context_window(self):
        ctx = get_context_window(model_id="gpt-6.1-sol")
        assert ctx is not None
        assert ctx > 0

    def test_normalize_provider(self):
        assert normalize_provider(litellm_provider="anthropic") == "claude"
        assert normalize_provider(litellm_provider="openai") == "openai"
        assert normalize_provider(litellm_provider="gemini") == "gemini"
        assert normalize_provider(litellm_provider="xai") == "grok"

    def test_lookup_model(self):
        entry = lookup_model(model_id="gpt-6.1-sol")
        assert entry is not None
        assert "max_input_tokens" in entry
