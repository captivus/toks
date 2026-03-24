"""Configuration and setup wizard tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from count_tokens.config import load_config, save_config, CONFIG_DIR, CONFIG_FILE, ENV_FILE, get_web_context_window
from count_tokens.providers.base import Config, ProviderConfig
from count_tokens.setup import gather_config, run_setup, FixedPrompter


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config to a temp directory for each test."""
    test_config_dir = tmp_path / "count-tokens"
    test_config_dir.mkdir()
    monkeypatch.setattr("count_tokens.config.CONFIG_DIR", test_config_dir)
    monkeypatch.setattr("count_tokens.config.CONFIG_FILE", test_config_dir / "config.toml")
    monkeypatch.setattr("count_tokens.config.ENV_FILE", test_config_dir / ".env")
    monkeypatch.setattr("count_tokens.setup.CONFIG_FILE", test_config_dir / "config.toml")
    yield test_config_dir


class TestGatherConfig:
    def test_single_provider_gemini(self):
        prompter = FixedPrompter(answers={
            "Which providers": ["gemini"],
            "gemini API key": os.environ.get("GEMINI_API_KEY", "test-key"),
            "gemini plan": "Free",
            "coding agent": True,
            "coding agent use": "gemini-2.5-flash",
            "gemini model for the API": "gemini-2.5-flash",
            "default provider": "gemini",
        })
        config = gather_config(prompter=prompter, skip_validation=True)
        assert config is not None
        assert config.default_provider == "gemini"
        assert "gemini" in config.providers
        assert config.providers["gemini"].model == "gemini-2.5-flash"
        assert config.providers["gemini"].has_coding_agent is True
        assert config.providers["gemini"].agent_model == "gemini-2.5-flash"

    def test_multiple_providers(self):
        prompter = FixedPrompter(answers={
            "Which providers": ["claude", "openai"],
            "claude API key": "sk-test-claude",
            "claude plan": "Free",
            "claude.*coding agent?": True,
            "claude.*coding agent use": "claude-opus-4-6",
            "claude model for the API": "claude-sonnet-4-6",
            "openai API key": "sk-test-openai",
            "openai plan": "Free",
            "openai.*coding agent?": True,
            "openai.*coding agent use": "gpt-4o-mini",
            "openai model for the API": "gpt-4o-mini",
            "default provider": "claude",
        })
        config = gather_config(prompter=prompter, skip_validation=True)
        assert config is not None
        assert config.default_provider == "claude"
        assert len(config.providers) == 2

    def test_no_providers_returns_none(self):
        prompter = FixedPrompter(answers={
            "Which providers": [],
        })
        config = gather_config(prompter=prompter, skip_validation=True)
        assert config is None

    def test_grok_no_coding_agent(self):
        prompter = FixedPrompter(answers={
            "Which providers": ["grok"],
            "grok API key": "xai-test-key",
            "grok plan": "Free",
            "grok model for the API": "grok-3",
            "default provider": "grok",
        })
        config = gather_config(prompter=prompter, skip_validation=True)
        assert config is not None
        assert config.providers["grok"].has_coding_agent is False
        assert config.providers["grok"].agent_model is None


class TestSaveAndLoadConfig:
    def test_round_trip(self, isolated_config):
        config = Config(
            default_provider="gemini",
            providers={
                "gemini": ProviderConfig(
                    api_key="test-gemini-key",
                    model="gemini-2.5-flash",
                    agent_model="gemini-2.5-flash",
                    plan="ai_pro",
                    has_coding_agent=True,
                ),
            },
        )
        save_config(config=config)

        config_file = isolated_config / "config.toml"
        env_file = isolated_config / ".env"
        assert config_file.exists()
        assert env_file.exists()

        loaded = load_config()
        assert loaded is not None
        assert loaded.default_provider == "gemini"
        assert "gemini" in loaded.providers
        assert loaded.providers["gemini"].model == "gemini-2.5-flash"
        assert loaded.providers["gemini"].agent_model == "gemini-2.5-flash"
        assert loaded.providers["gemini"].plan == "ai_pro"
        assert loaded.providers["gemini"].has_coding_agent is True

    def test_multiple_providers_round_trip(self, isolated_config):
        config = Config(
            default_provider="claude",
            providers={
                "claude": ProviderConfig(
                    api_key="sk-ant-test",
                    model="claude-sonnet-4-6",
                    agent_model="claude-opus-4-6",
                    plan="max_20x",
                    has_coding_agent=True,
                ),
                "openai": ProviderConfig(
                    api_key="sk-openai-test",
                    model="gpt-4o-mini",
                    agent_model="gpt-4o-mini",
                    plan="plus",
                    has_coding_agent=True,
                ),
            },
        )
        save_config(config=config)
        loaded = load_config()
        assert loaded is not None
        assert len(loaded.providers) == 2
        assert loaded.providers["claude"].plan == "max_20x"
        assert loaded.providers["openai"].plan == "plus"

    def test_no_config_returns_none(self, isolated_config):
        loaded = load_config()
        assert loaded is None


class TestRunSetup:
    def test_full_setup_flow(self, isolated_config):
        prompter = FixedPrompter(answers={
            "Which providers": ["gemini"],
            "gemini API key": os.environ.get("GEMINI_API_KEY", "test-key"),
            "gemini plan": "AI Pro ($19.99/mo)",
            "coding agent?": True,
            "coding agent use": "gemini-2.5-flash",
            "model for the API": "gemini-2.5-flash",
            "default provider": "gemini",
        })
        run_setup(prompter=prompter, skip_validation=True)

        config_file = isolated_config / "config.toml"
        assert config_file.exists()

        loaded = load_config()
        assert loaded is not None
        assert loaded.default_provider == "gemini"

    def test_re_run_setup_preserves_existing(self, isolated_config):
        config = Config(
            default_provider="gemini",
            providers={
                "gemini": ProviderConfig(
                    api_key="original-key",
                    model="gemini-2.5-flash",
                    plan="free",
                    has_coding_agent=False,
                ),
            },
        )
        save_config(config=config)

        prompter = FixedPrompter(answers={
            "Which providers": ["gemini"],
            "gemini API key": "updated-key",
            "gemini plan": "Free",
            "coding agent?": True,
            "coding agent use": "gemini-2.5-flash",
            "model for the API": "gemini-2.5-flash",
            "default provider": "gemini",
        })
        run_setup(prompter=prompter, skip_validation=True)

        loaded = load_config()
        assert loaded is not None
        assert loaded.providers["gemini"].has_coding_agent is True


class TestWebContextWindows:
    def test_claude_free(self):
        assert get_web_context_window(provider="claude", plan="free") == 200_000

    def test_claude_enterprise(self):
        assert get_web_context_window(provider="claude", plan="enterprise") == 500_000

    def test_openai_free(self):
        assert get_web_context_window(provider="openai", plan="free") == 16_000

    def test_openai_plus(self):
        assert get_web_context_window(provider="openai", plan="plus") == 32_000

    def test_openai_pro(self):
        assert get_web_context_window(provider="openai", plan="pro") == 128_000

    def test_gemini_free(self):
        assert get_web_context_window(provider="gemini", plan="free") == 32_000

    def test_gemini_ai_pro(self):
        assert get_web_context_window(provider="gemini", plan="ai_pro") == 1_000_000

    def test_grok_supergrok(self):
        assert get_web_context_window(provider="grok", plan="supergrok") == 128_000

    def test_unknown_returns_none(self):
        assert get_web_context_window(provider="unknown", plan="free") is None
