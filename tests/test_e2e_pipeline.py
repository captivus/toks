"""End-to-end pipeline tests.

Tests the FULL path: config → model resolution → API call → output.
This single test file would have caught every bug the user hit during
development — bad model names, corrupted .env, broken payload formats —
because it exercises the entire pipeline from config through to API response.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from dotenv import load_dotenv

from count_tokens.cli import app
from count_tokens.config import save_config
from count_tokens.providers.base import Config, ProviderConfig
from count_tokens.setup import gather_config, FixedPrompter

load_dotenv()
load_dotenv(Path.home() / ".config" / "count-tokens" / ".env")

FIXTURES = Path(__file__).parent / "fixtures"

# Known-valid models confirmed by preflight tests
VALID_MODELS = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "grok": "grok-3",
}

VALID_AGENT_MODELS = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
}

ENV_KEYS = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "grok": "GROK_API_KEY",
}


def _make_config_for_provider(*, provider: str, tmp_dir: Path) -> None:
    """Create a minimal config for a single provider in the given directory."""
    api_key = os.environ.get(ENV_KEYS[provider], "")
    config = Config(
        default_provider=provider,
        providers={
            provider: ProviderConfig(
                api_key=api_key,
                model=VALID_MODELS[provider],
                agent_model=VALID_AGENT_MODELS.get(provider),
                plan="free",
                has_coding_agent=provider != "grok",
            ),
        },
    )
    save_config(config=config)


def _run_cli(*, args: list[str]) -> tuple[int, str]:
    """Run the CLI with the current environment and return (exit_code, output)."""
    runner = CliRunner(env=dict(os.environ))
    result = runner.invoke(app, args)
    return result.exit_code, result.output


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Redirect config to tmp for test isolation."""
    config_dir = tmp_path / "count-tokens"
    config_dir.mkdir()
    monkeypatch.setattr("count_tokens.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("count_tokens.config.CONFIG_FILE", config_dir / "config.toml")
    monkeypatch.setattr("count_tokens.config.ENV_FILE", config_dir / ".env")
    return config_dir


@pytest.mark.claude
class TestClaudePipeline:
    def test_single_file_via_for(self, isolated_config, monkeypatch):
        _make_config_for_provider(provider="claude", tmp_dir=isolated_config)
        code, output = _run_cli(args=[str(FIXTURES / "hello.txt"), "--for", "claude", "--no-progress", "-q"])
        assert code == 0, f"Exit {code}: {output}"
        assert int(output.strip()) > 0

    def test_directory_via_for(self, isolated_config, monkeypatch):
        _make_config_for_provider(provider="claude", tmp_dir=isolated_config)
        code, output = _run_cli(args=[str(FIXTURES), "--for", "claude", "--no-progress"])
        assert code == 0, f"Exit {code}: {output}"
        assert "Total:" in output


@pytest.mark.openai
class TestOpenAIPipeline:
    def test_single_file_via_for(self, isolated_config, monkeypatch):
        _make_config_for_provider(provider="openai", tmp_dir=isolated_config)
        code, output = _run_cli(args=[str(FIXTURES / "hello.txt"), "--for", "openai", "--no-progress", "-q"])
        assert code == 0, f"Exit {code}: {output}"
        assert int(output.strip()) > 0

    def test_directory_via_for(self, isolated_config, monkeypatch):
        _make_config_for_provider(provider="openai", tmp_dir=isolated_config)
        code, output = _run_cli(args=[str(FIXTURES), "--for", "openai", "--no-progress"])
        assert code == 0, f"Exit {code}: {output}"
        assert "Total:" in output


@pytest.mark.gemini
class TestGeminiPipeline:
    def test_single_file_via_for(self, isolated_config, monkeypatch):
        _make_config_for_provider(provider="gemini", tmp_dir=isolated_config)
        code, output = _run_cli(args=[str(FIXTURES / "hello.txt"), "--for", "gemini", "--no-progress", "-q"])
        assert code == 0, f"Exit {code}: {output}"
        assert int(output.strip()) > 0

    def test_directory_via_for(self, isolated_config, monkeypatch):
        _make_config_for_provider(provider="gemini", tmp_dir=isolated_config)
        code, output = _run_cli(args=[str(FIXTURES), "--for", "gemini", "--no-progress"])
        assert code == 0, f"Exit {code}: {output}"
        assert "Total:" in output


@pytest.mark.grok
class TestGrokPipeline:
    def test_single_file_via_for(self, isolated_config, monkeypatch):
        _make_config_for_provider(provider="grok", tmp_dir=isolated_config)
        code, output = _run_cli(args=[str(FIXTURES / "hello.txt"), "--for", "grok", "--no-progress", "-q"])
        assert code == 0, f"Exit {code}: {output}"
        assert int(output.strip()) > 0

    def test_directory_via_for(self, isolated_config, monkeypatch):
        _make_config_for_provider(provider="grok", tmp_dir=isolated_config)
        code, output = _run_cli(args=[str(FIXTURES), "--for", "grok", "--no-progress"])
        assert code == 0, f"Exit {code}: {output}"
        assert "Total:" in output


class TestConfigRoundTrip:
    def test_env_idempotent(self, isolated_config):
        """Save → load → save → load. Values must be identical."""
        config = Config(
            default_provider="claude",
            providers={
                "claude": ProviderConfig(
                    api_key="sk-ant-abc123xyz",
                    model="claude-sonnet-4-6",
                    plan="free",
                    has_coding_agent=False,
                ),
            },
        )
        save_config(config=config)
        loaded1 = __import__("count_tokens.config", fromlist=["load_config"]).load_config()
        save_config(config=loaded1)
        loaded2 = __import__("count_tokens.config", fromlist=["load_config"]).load_config()
        assert loaded1.providers["claude"].api_key == loaded2.providers["claude"].api_key
        assert loaded2.providers["claude"].api_key == "sk-ant-abc123xyz"

    def test_env_special_characters(self, isolated_config):
        """API keys with special chars survive round-trip."""
        config = Config(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(
                    api_key="sk-proj-abc=123+xyz/test",
                    model="gpt-4o-mini",
                    plan="free",
                    has_coding_agent=False,
                ),
            },
        )
        save_config(config=config)
        loaded = __import__("count_tokens.config", fromlist=["load_config"]).load_config()
        assert loaded.providers["openai"].api_key == "sk-proj-abc=123+xyz/test"
