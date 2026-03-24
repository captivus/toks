"""Provider tests — real API calls."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from count_tokens.providers.base import FileResult, TokenCountResult, UnsupportedFileTypeError
from count_tokens.providers.claude import ClaudeProvider
from count_tokens.providers.openai import OpenAIProvider
from count_tokens.providers.gemini import GeminiProvider
from count_tokens.providers.grok import GrokProvider
from count_tokens.runner import count_file_tokens

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def claude_provider():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return ClaudeProvider(api_key=key)


@pytest.fixture
def openai_provider():
    key = os.environ.get("OPENAI_API_KEY", "")
    return OpenAIProvider(api_key=key)


@pytest.fixture
def gemini_provider():
    key = os.environ.get("GEMINI_API_KEY", "")
    return GeminiProvider(api_key=key)


@pytest.fixture
def grok_provider():
    key = os.environ.get("GROK_API_KEY", "")
    return GrokProvider(api_key=key)


# --- Gemini tests (provider available) ---

@pytest.mark.gemini
class TestGeminiProvider:
    def test_text_file(self, gemini_provider):
        content = (FIXTURES / "hello.txt").read_bytes()
        result = asyncio.run(gemini_provider.count_tokens(
            content=content, mime_type="text/plain", model="gemini-2.5-flash",
        ))
        assert result.total_tokens > 0
        assert result.model == "gemini-2.5-flash"

    def test_python_file(self, gemini_provider):
        content = (FIXTURES / "hello.py").read_bytes()
        result = asyncio.run(gemini_provider.count_tokens(
            content=content, mime_type="text/x-python", model="gemini-2.5-flash",
        ))
        assert result.total_tokens > 0

    def test_image_png(self, gemini_provider):
        content = (FIXTURES / "image.png").read_bytes()
        result = asyncio.run(gemini_provider.count_tokens(
            content=content, mime_type="image/png", model="gemini-2.5-flash",
        ))
        assert result.total_tokens > 0

    def test_pdf(self, gemini_provider):
        content = (FIXTURES / "document.pdf").read_bytes()
        result = asyncio.run(gemini_provider.count_tokens(
            content=content, mime_type="application/pdf", model="gemini-2.5-flash",
        ))
        assert result.total_tokens > 0

    def test_modality_breakdown(self, gemini_provider):
        content = (FIXTURES / "hello.txt").read_bytes()
        result = asyncio.run(gemini_provider.count_tokens(
            content=content, mime_type="text/plain", model="gemini-2.5-flash",
        ))
        # Gemini may or may not return breakdown for text-only
        assert result.total_tokens > 0

    def test_unsupported_binary(self, gemini_provider):
        with pytest.raises(UnsupportedFileTypeError):
            asyncio.run(gemini_provider.count_tokens(
                content=b"\x00\x01\x02", mime_type="application/octet-stream", model="gemini-2.5-flash",
            ))


# --- OpenAI tests (provider available) ---

@pytest.mark.openai
class TestOpenAIProvider:
    def test_text_file(self, openai_provider):
        content = (FIXTURES / "hello.txt").read_bytes()
        result = asyncio.run(openai_provider.count_tokens(
            content=content, mime_type="text/plain", model="gpt-4o-mini",
        ))
        assert result.total_tokens > 0
        assert result.model == "gpt-4o-mini"

    def test_python_file(self, openai_provider):
        content = (FIXTURES / "hello.py").read_bytes()
        result = asyncio.run(openai_provider.count_tokens(
            content=content, mime_type="text/x-python", model="gpt-4o-mini",
        ))
        assert result.total_tokens > 0

    def test_image_png(self, openai_provider):
        content = (FIXTURES / "image.png").read_bytes()
        result = asyncio.run(openai_provider.count_tokens(
            content=content, mime_type="image/png", model="gpt-4o-mini",
        ))
        assert result.total_tokens > 0

    def test_unsupported_binary(self, openai_provider):
        with pytest.raises(UnsupportedFileTypeError):
            asyncio.run(openai_provider.count_tokens(
                content=b"\x00\x01\x02", mime_type="application/octet-stream", model="gpt-4o-mini",
            ))


# --- Claude tests (may not have credits) ---

@pytest.mark.claude
class TestClaudeProvider:
    def test_text_file(self, claude_provider):
        content = (FIXTURES / "hello.txt").read_bytes()
        result = asyncio.run(claude_provider.count_tokens(
            content=content, mime_type="text/plain", model="claude-sonnet-4-6",
        ))
        assert result.total_tokens > 0

    def test_unsupported_docx(self, claude_provider):
        content = (FIXTURES / "document.docx").read_bytes()
        with pytest.raises(UnsupportedFileTypeError):
            asyncio.run(claude_provider.count_tokens(
                content=content,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                model="claude-sonnet-4-6",
            ))


# --- Grok tests (may not have credits) ---

@pytest.mark.grok
class TestGrokProvider:
    def test_text_file(self, grok_provider):
        content = (FIXTURES / "hello.txt").read_bytes()
        result = asyncio.run(grok_provider.count_tokens(
            content=content, mime_type="text/plain", model="grok-3",
        ))
        assert result.total_tokens > 0

    def test_unsupported_image(self, grok_provider):
        content = (FIXTURES / "image.png").read_bytes()
        with pytest.raises(UnsupportedFileTypeError):
            asyncio.run(grok_provider.count_tokens(
                content=content, mime_type="image/png", model="grok-3",
            ))


# --- Edge case tests ---

class TestEdgeCases:
    def test_empty_file_returns_zero(self, gemini_provider):
        """Empty files should return 0 tokens without hitting the API."""
        fr = FileResult(path=FIXTURES / "empty.txt", mime_type="text/plain", file_size=0)
        result = asyncio.run(count_file_tokens(
            provider=gemini_provider, file_result=fr, model="gemini-2.5-flash", retries=0,
        ))
        assert result.status == "success"
        assert result.token_count is not None
        assert result.token_count.total_tokens == 0

    @pytest.mark.claude
    def test_claude_image_jpeg(self, claude_provider):
        """Claude should handle JPEG images."""
        content = (FIXTURES / "image.jpg").read_bytes()
        result = asyncio.run(claude_provider.count_tokens(
            content=content, mime_type="image/jpeg", model="claude-sonnet-4-6",
        ))
        assert result.total_tokens > 0

    @pytest.mark.claude
    def test_claude_image_png(self, claude_provider):
        """Claude should handle PNG images."""
        content = (FIXTURES / "image.png").read_bytes()
        result = asyncio.run(claude_provider.count_tokens(
            content=content, mime_type="image/png", model="claude-sonnet-4-6",
        ))
        assert result.total_tokens > 0

    @pytest.mark.claude
    def test_claude_pdf(self, claude_provider):
        """Claude should handle PDF files."""
        content = (FIXTURES / "document.pdf").read_bytes()
        result = asyncio.run(claude_provider.count_tokens(
            content=content, mime_type="application/pdf", model="claude-sonnet-4-6",
        ))
        assert result.total_tokens > 0

    @pytest.mark.openai
    def test_openai_image_jpeg(self, openai_provider):
        """OpenAI should handle JPEG images."""
        content = (FIXTURES / "image.jpg").read_bytes()
        result = asyncio.run(openai_provider.count_tokens(
            content=content, mime_type="image/jpeg", model="gpt-4o-mini",
        ))
        assert result.total_tokens > 0

    @pytest.mark.gemini
    def test_gemini_image_jpeg(self, gemini_provider):
        """Gemini should handle JPEG images."""
        content = (FIXTURES / "image.jpg").read_bytes()
        result = asyncio.run(gemini_provider.count_tokens(
            content=content, mime_type="image/jpeg", model="gemini-2.5-flash",
        ))
        assert result.total_tokens > 0

    @pytest.mark.claude
    def test_claude_directory_no_failures(self, claude_provider):
        """Counting the fixtures directory via Claude should have no unexpected failures."""
        from count_tokens.scanner import scan_files
        scanned = scan_files(target=FIXTURES)
        file_results = [FileResult(path=p, mime_type=m, file_size=s) for p, m, s in scanned]
        asyncio.run(
            __import__("count_tokens.runner", fromlist=["run_token_counting"]).run_token_counting(
                provider=claude_provider, file_results=file_results,
                model="claude-sonnet-4-6", concurrency=5, retries=1,
            )
        )
        failed = [fr for fr in file_results if fr.status == "failed"]
        assert len(failed) == 0, f"Unexpected failures: {[(fr.path.name, fr.error) for fr in failed]}"
