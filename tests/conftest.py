"""Shared fixtures and pytest configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

FIXTURES_DIR = Path(__file__).parent / "fixtures"

load_dotenv()
load_dotenv(Path.home() / ".config" / "count-tokens" / ".env")


def has_api_key(*, env_var: str) -> bool:
    return bool(os.environ.get(env_var))


skip_no_anthropic = pytest.mark.skipif(
    not has_api_key(env_var="ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
skip_no_openai = pytest.mark.skipif(
    not has_api_key(env_var="OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
skip_no_gemini = pytest.mark.skipif(
    not has_api_key(env_var="GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set",
)
skip_no_grok = pytest.mark.skipif(
    not has_api_key(env_var="GROK_API_KEY"),
    reason="GROK_API_KEY not set",
)


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def tree_dir():
    return FIXTURES_DIR / "tree"
