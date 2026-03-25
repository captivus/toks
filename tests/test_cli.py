"""CLI integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from dotenv import load_dotenv

from toks.cli import app

load_dotenv()
load_dotenv(Path.home() / ".config" / "toks" / ".env")

FIXTURES = Path(__file__).parent / "fixtures"


def make_runner():
    return CliRunner(env=dict(os.environ))


class TestBasicCLI:
    def test_version(self):
        result = make_runner().invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "toks" in result.output

    def test_no_args_shows_help(self):
        result = make_runner().invoke(app, [])
        assert result.exit_code == 0
        assert "toks" in result.output.lower() or "usage" in result.output.lower()

    def test_nonexistent_file(self):
        result = make_runner().invoke(app, ["/nonexistent/file.txt", "--model", "gemini-2.5-flash"])
        assert result.exit_code != 0

    def test_no_provider_no_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("toks.config.CONFIG_FILE", tmp_path / "nonexistent" / "config.toml")
        monkeypatch.setattr("toks.config.ENV_FILE", tmp_path / "nonexistent" / ".env")
        env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        result = CliRunner(env=env).invoke(app, [str(FIXTURES / "hello.txt")])
        assert result.exit_code == 1


@pytest.mark.gemini
class TestGeminiCLI:
    def test_single_file(self):
        result = make_runner().invoke(app, [str(FIXTURES / "hello.txt"), "--model", "gemini-2.5-flash", "--no-progress"])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert "tokens" in result.output.lower() or result.output.strip().isdigit()

    def test_directory(self):
        result = make_runner().invoke(app, [str(FIXTURES), "--model", "gemini-2.5-flash", "--no-progress"])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert "Total:" in result.output

    def test_quiet_mode(self):
        result = make_runner().invoke(app, [str(FIXTURES / "hello.txt"), "--model", "gemini-2.5-flash", "-q"])
        output = result.output.strip()
        assert output.isdigit(), f"Expected integer, got: {repr(output)}"
        assert int(output) > 0

    def test_summary_mode(self):
        result = make_runner().invoke(app, [str(FIXTURES / "hello.txt"), "--model", "gemini-2.5-flash", "--summary"])
        assert "Total:" in result.output

    def test_glob_filter(self):
        result = make_runner().invoke(app, [str(FIXTURES), "--model", "gemini-2.5-flash", "--glob", "*.py", "--no-progress"])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert "hello.py" in result.output

    def test_max_size(self):
        result = make_runner().invoke(app, [str(FIXTURES), "--model", "gemini-2.5-flash", "--max-size", "10", "--no-progress"])
        assert result.exit_code == 0, f"Output: {result.output}"


@pytest.mark.openai
class TestOpenAICLI:
    def test_single_file(self):
        result = make_runner().invoke(app, [str(FIXTURES / "hello.txt"), "--model", "gpt-4o-mini", "--no-progress"])
        assert result.exit_code == 0, f"Output: {result.output}"

    def test_quiet_mode(self):
        result = make_runner().invoke(app, [str(FIXTURES / "hello.txt"), "--model", "gpt-4o-mini", "-q"])
        output = result.output.strip()
        assert output.isdigit(), f"Expected integer, got: {repr(output)}"
        assert int(output) > 0
