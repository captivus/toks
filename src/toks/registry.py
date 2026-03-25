"""LiteLLM model registry: fetch, cache, and lookup."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

REGISTRY_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
CACHE_DIR = Path.home() / ".config" / "toks"
CACHE_FILE = CACHE_DIR / "models.json"

PROVIDER_MAP = {
    "anthropic": "claude",
    "openai": "openai",
    "text-completion-openai": "openai",
    "vertex_ai-language-models": "gemini",
    "vertex_ai": "gemini",
    "gemini": "gemini",
    "xai": "grok",
}


def fetch_registry() -> dict:
    response = httpx.get(REGISTRY_URL, timeout=30.0)
    response.raise_for_status()
    return response.json()


def save_cache(*, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data))


def load_cache() -> dict | None:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return None


def refresh_registry() -> dict:
    data = fetch_registry()
    save_cache(data=data)
    return data


def get_registry() -> dict:
    data = load_cache()
    if data is None:
        data = refresh_registry()
    return data


def normalize_provider(*, litellm_provider: str) -> str | None:
    for prefix, name in PROVIDER_MAP.items():
        if litellm_provider.startswith(prefix):
            return name
    return None


def lookup_model(*, model_id: str, registry: dict | None = None) -> dict | None:
    if registry is None:
        registry = get_registry()

    if model_id in registry:
        entry = registry[model_id]
        if isinstance(entry, dict):
            return entry

    for key, entry in registry.items():
        if not isinstance(entry, dict):
            continue
        if key.endswith(f"/{model_id}") or key == model_id:
            return entry

    return None


def infer_provider(*, model_id: str, registry: dict | None = None) -> str | None:
    entry = lookup_model(model_id=model_id, registry=registry)
    if entry is None:
        return None
    litellm_provider = entry.get("litellm_provider", "")
    return normalize_provider(litellm_provider=litellm_provider)


def get_context_window(*, model_id: str, registry: dict | None = None) -> int | None:
    entry = lookup_model(model_id=model_id, registry=registry)
    if entry is None:
        return None
    return entry.get("max_input_tokens")


def list_models_for_provider(*, provider: str, registry: dict | None = None) -> list[dict]:
    if registry is None:
        registry = get_registry()
    results = []
    for key, entry in registry.items():
        if not isinstance(entry, dict):
            continue
        litellm_provider = entry.get("litellm_provider", "")
        normalized = normalize_provider(litellm_provider=litellm_provider)
        if normalized == provider:
            max_input = entry.get("max_input_tokens")
            if max_input:
                results.append({
                    "model_id": key,
                    "max_input_tokens": max_input,
                    "max_output_tokens": entry.get("max_output_tokens"),
                })
    results.sort(key=lambda x: x["model_id"])
    return results
