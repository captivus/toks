"""Scanner tests — file discovery, filtering, MIME detection."""

from __future__ import annotations

from pathlib import Path

from count_tokens.scanner import detect_mime_type, is_binary_mime, parse_size, scan_files

FIXTURES = Path(__file__).parent / "fixtures"


class TestDetectMimeType:
    def test_python_file(self):
        assert detect_mime_type(path=Path("test.py")).startswith("text/")

    def test_text_file(self):
        assert detect_mime_type(path=Path("test.txt")) == "text/plain"

    def test_png(self):
        assert detect_mime_type(path=Path("test.png")) == "image/png"

    def test_pdf(self):
        assert detect_mime_type(path=Path("test.pdf")) == "application/pdf"

    def test_unknown_defaults_to_text(self):
        assert detect_mime_type(path=Path("test.xyz123")) == "text/plain"

    def test_tsx(self):
        result = detect_mime_type(path=Path("test.tsx"))
        assert result == "text/plain" or result.startswith("text/")


class TestIsBinaryMime:
    def test_text_is_not_binary(self):
        assert not is_binary_mime(mime_type="text/plain")
        assert not is_binary_mime(mime_type="text/x-python")

    def test_image_is_not_binary(self):
        assert not is_binary_mime(mime_type="image/png")

    def test_pdf_is_not_binary(self):
        assert not is_binary_mime(mime_type="application/pdf")

    def test_json_is_not_binary(self):
        assert not is_binary_mime(mime_type="application/json")

    def test_exe_is_binary(self):
        assert is_binary_mime(mime_type="application/octet-stream")

    def test_zip_is_binary(self):
        assert is_binary_mime(mime_type="application/zip")

    def test_docx_is_not_binary(self):
        assert not is_binary_mime(mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


class TestParseSize:
    def test_kb(self):
        assert parse_size(size_str="10KB") == 10_000

    def test_mb(self):
        assert parse_size(size_str="50MB") == 50_000_000

    def test_gb(self):
        assert parse_size(size_str="1GB") == 1_000_000_000

    def test_bare_number(self):
        assert parse_size(size_str="1000") == 1000


class TestScanFiles:
    def test_scan_fixtures(self):
        results = scan_files(target=FIXTURES)
        paths = [r[0].name for r in results]
        assert "hello.txt" in paths
        assert "hello.py" in paths

    def test_glob_filter(self):
        results = scan_files(target=FIXTURES, glob_pattern="*.py")
        paths = [r[0].name for r in results]
        assert all(p.endswith(".py") for p in paths)

    def test_max_size_filter(self):
        results_all = scan_files(target=FIXTURES)
        results_small = scan_files(target=FIXTURES, max_size=50)
        assert len(results_small) <= len(results_all)

    def test_excludes_binary_by_default(self):
        results = scan_files(target=FIXTURES)
        mimes = [r[1] for r in results]
        assert "application/zip" not in mimes

    def test_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        results = scan_files(target=empty)
        assert results == []
