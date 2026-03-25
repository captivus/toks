"""Configuration management: reading, writing, and the setup wizard."""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomli_w
from dotenv import dotenv_values

from toks.providers.base import Config, ProviderConfig

CONFIG_DIR = Path.home() / ".config" / "toks"
CONFIG_FILE = CONFIG_DIR / "config.toml"
ENV_FILE = CONFIG_DIR / ".env"

WEB_CONTEXT_WINDOWS: dict[str, dict[str, int]] = {
    "claude": {
        "free": 200_000, "pro": 200_000, "max_5x": 200_000, "max_20x": 200_000,
        "team_standard": 200_000, "team_premium": 200_000, "enterprise": 500_000,
    },
    "openai": {
        "free": 16_000, "go": 32_000, "plus": 32_000, "pro": 128_000,
        "business": 32_000, "enterprise": 128_000,
    },
    "gemini": {
        "free": 32_000, "ai_plus": 128_000, "ai_pro": 1_000_000, "ai_ultra": 1_000_000,
    },
    "grok": {
        "free": 128_000, "x_premium": 128_000, "x_premium_plus": 128_000,
        "supergrok": 128_000, "supergrok_heavy": 256_000,
    },
}


def get_web_context_window(*, provider: str, plan: str) -> int | None:
    provider_plans = WEB_CONTEXT_WINDOWS.get(provider, {})
    return provider_plans.get(plan)


def _clean_api_key(*, value: str, env_key: str) -> str:
    """Clean up API key values that may have been corrupted by previous save bugs."""
    if not value:
        return value
    if value.startswith(f'{env_key}='):
        value = value[len(f'{env_key}='):]
    value = value.strip('"').strip("'")
    return value


def load_config() -> Config | None:
    if not CONFIG_FILE.exists():
        return None

    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)

    env_vars = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

    from toks.providers import PROVIDER_ENV_KEYS

    providers = {}
    for name, provider_data in data.get("providers", {}).items():
        env_key = PROVIDER_ENV_KEYS.get(name, "")
        api_key = _clean_api_key(value=env_vars.get(env_key, ""), env_key=env_key)
        providers[name] = ProviderConfig(
            api_key=api_key,
            model=provider_data.get("model", ""),
            agent_model=provider_data.get("agent_model"),
            plan=provider_data.get("plan", "free"),
            has_coding_agent=provider_data.get("has_coding_agent", False),
        )

    return Config(
        default_provider=data.get("default_provider", ""),
        providers=providers,
    )


def save_config(*, config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    toml_data: dict = {"default_provider": config.default_provider, "providers": {}}
    for name, pc in config.providers.items():
        provider_dict: dict = {"model": pc.model, "plan": pc.plan, "has_coding_agent": pc.has_coding_agent}
        if pc.agent_model:
            provider_dict["agent_model"] = pc.agent_model
        toml_data["providers"][name] = provider_dict

    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(toml_data, f)

    from toks.providers import PROVIDER_ENV_KEYS
    lines = []
    for name, pc in config.providers.items():
        env_key = PROVIDER_ENV_KEYS.get(name, "")
        if env_key and pc.api_key:
            lines.append(f"{env_key}={pc.api_key}")
    ENV_FILE.write_text("\n".join(lines) + "\n" if lines else "")


def load_env_api_key(*, provider: str) -> str | None:
    from toks.providers import PROVIDER_ENV_KEYS

    env_key = PROVIDER_ENV_KEYS.get(provider, "")
    if not env_key:
        return None

    if ENV_FILE.exists():
        env_vars = dotenv_values(ENV_FILE)
        val = env_vars.get(env_key)
        if val:
            return _clean_api_key(value=val, env_key=env_key)

    local_env = dotenv_values(".env")
    val = local_env.get(env_key)
    if val:
        return _clean_api_key(value=val, env_key=env_key)

    import os
    return os.environ.get(env_key)
