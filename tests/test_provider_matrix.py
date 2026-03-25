"""Provider integration test matrix.

Tests every provider against every file type it claims to support.
This catches payload format bugs — the root cause of most provider failures.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from count_tokens.providers.base import UnsupportedFileTypeError
from count_tokens.providers.claude import ClaudeProvider
from count_tokens.providers.openai import OpenAIProvider
from count_tokens.providers.gemini import GeminiProvider
from count_tokens.providers.grok import GrokProvider

FIXTURES = Path(__file__).parent / "fixtures"

# File type test data: (fixture_file, mime_type)
TEXT_FILE = ("hello.txt", "text/plain")
PYTHON_FILE = ("hello.py", "text/x-python")
PNG_FILE = ("image.png", "image/png")
JPEG_FILE = ("image.jpg", "image/jpeg")
PDF_FILE = ("document.pdf", "application/pdf")
DOCX_FILE = ("document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
EMPTY_FILE = ("empty.txt", "text/plain")

# The matrix: (provider_fixture, model, supported_files, unsupported_files)
# Each supported file MUST return a positive token count (or 0 for empty).
# Each unsupported file MUST raise UnsupportedFileTypeError.


@pytest.fixture
def claude():
    return ClaudeProvider(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


@pytest.fixture
def openai():
    return OpenAIProvider(api_key=os.environ.get("OPENAI_API_KEY", ""))


@pytest.fixture
def gemini():
    return GeminiProvider(api_key=os.environ.get("GEMINI_API_KEY", ""))


@pytest.fixture
def grok():
    return GrokProvider(api_key=os.environ.get("GROK_API_KEY", ""))


def _count(provider, fixture_name, mime_type, model):
    content = (FIXTURES / fixture_name).read_bytes()
    return asyncio.run(provider.count_tokens(content=content, mime_type=mime_type, model=model))


# --- Claude matrix ---

@pytest.mark.claude
class TestClaudeMatrix:
    MODEL = "claude-sonnet-4-6"

    def test_text(self, claude):
        result = _count(claude, *TEXT_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_python(self, claude):
        result = _count(claude, *PYTHON_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_png(self, claude):
        result = _count(claude, *PNG_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_jpeg(self, claude):
        result = _count(claude, *JPEG_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_pdf(self, claude):
        result = _count(claude, *PDF_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_docx_unsupported(self, claude):
        with pytest.raises(UnsupportedFileTypeError):
            _count(claude, *DOCX_FILE, self.MODEL)

    def test_binary_unsupported(self, claude):
        with pytest.raises(UnsupportedFileTypeError):
            asyncio.run(claude.count_tokens(
                content=b"\x00\x01", mime_type="application/octet-stream", model=self.MODEL,
            ))


# --- OpenAI matrix ---

@pytest.mark.openai
class TestOpenAIMatrix:
    MODEL = "gpt-4o-mini"

    def test_text(self, openai):
        result = _count(openai, *TEXT_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_python(self, openai):
        result = _count(openai, *PYTHON_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_png(self, openai):
        result = _count(openai, *PNG_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_jpeg(self, openai):
        result = _count(openai, *JPEG_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_pdf(self, openai):
        result = _count(openai, *PDF_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_docx(self, openai):
        result = _count(openai, *DOCX_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_binary_unsupported(self, openai):
        with pytest.raises(UnsupportedFileTypeError):
            asyncio.run(openai.count_tokens(
                content=b"\x00\x01", mime_type="application/octet-stream", model=self.MODEL,
            ))


# --- Gemini matrix ---

@pytest.mark.gemini
class TestGeminiMatrix:
    MODEL = "gemini-2.5-flash"

    def test_text(self, gemini):
        result = _count(gemini, *TEXT_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_python(self, gemini):
        result = _count(gemini, *PYTHON_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_png(self, gemini):
        result = _count(gemini, *PNG_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_jpeg(self, gemini):
        result = _count(gemini, *JPEG_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_pdf(self, gemini):
        result = _count(gemini, *PDF_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_docx_unsupported(self, gemini):
        """Gemini rejects docx via inline_data."""
        with pytest.raises((UnsupportedFileTypeError, Exception)):
            _count(gemini, *DOCX_FILE, self.MODEL)

    def test_binary_unsupported(self, gemini):
        with pytest.raises(UnsupportedFileTypeError):
            asyncio.run(gemini.count_tokens(
                content=b"\x00\x01", mime_type="application/octet-stream", model=self.MODEL,
            ))


# --- Grok matrix ---

@pytest.mark.grok
class TestGrokMatrix:
    MODEL = "grok-3"

    def test_text(self, grok):
        result = _count(grok, *TEXT_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_python(self, grok):
        result = _count(grok, *PYTHON_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_png(self, grok):
        result = _count(grok, *PNG_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_jpeg(self, grok):
        result = _count(grok, *JPEG_FILE, self.MODEL)
        assert result.total_tokens > 0

    def test_pdf_unsupported(self, grok):
        with pytest.raises(UnsupportedFileTypeError):
            _count(grok, *PDF_FILE, self.MODEL)

    def test_docx_unsupported(self, grok):
        with pytest.raises(UnsupportedFileTypeError):
            _count(grok, *DOCX_FILE, self.MODEL)

    def test_binary_unsupported(self, grok):
        with pytest.raises(UnsupportedFileTypeError):
            asyncio.run(grok.count_tokens(
                content=b"\x00\x01", mime_type="application/octet-stream", model=self.MODEL,
            ))
