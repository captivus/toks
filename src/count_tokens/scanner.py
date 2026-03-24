"""File discovery, gitignore handling, filtering, and MIME detection."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import pathspec


MAGIC_BYTES: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "application/pdf": [b"%PDF"],
}


def validate_content_matches_mime(*, content: bytes, mime_type: str) -> bool:
    expected = MAGIC_BYTES.get(mime_type)
    if expected is None:
        return True
    return any(content.startswith(prefix) for prefix in expected)


def detect_mime_type(*, path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        return "text/plain"
    return mime_type


def is_binary_mime(*, mime_type: str) -> bool:
    if mime_type.startswith("text/"):
        return False
    if mime_type.startswith("image/"):
        return False
    if mime_type in ("application/pdf", "application/json", "application/xml"):
        return False
    if mime_type.startswith("application/vnd.openxmlformats"):
        return False
    return True


def find_git_root(*, start: Path) -> Path | None:
    current = start.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    if (current / ".git").exists():
        return current
    return None


def load_gitignore_specs(*, git_root: Path, target: Path) -> pathspec.PathSpec | None:
    patterns: list[str] = []
    target_resolved = target.resolve()

    for dirpath, _, _ in os.walk(git_root):
        dirpath_path = Path(dirpath)
        gitignore = dirpath_path / ".gitignore"
        if gitignore.is_file():
            prefix = dirpath_path.relative_to(git_root)
            for line in gitignore.read_text(errors="replace").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    if str(prefix) != ".":
                        patterns.append(f"{prefix}/{stripped}")
                    else:
                        patterns.append(stripped)

    if not patterns:
        return None
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def parse_size(*, size_str: str) -> int:
    size_str = size_str.strip().upper()
    multipliers = {"KB": 1_000, "MB": 1_000_000, "GB": 1_000_000_000}
    for suffix, multiplier in multipliers.items():
        if size_str.endswith(suffix):
            return int(float(size_str[: -len(suffix)].strip()) * multiplier)
    return int(size_str)


def scan_files(
    *,
    target: Path,
    glob_pattern: str | None = None,
    max_size: int = 50_000_000,
    no_gitignore: bool = False,
    include_binary: bool = False,
) -> list[tuple[Path, str, int]]:
    """Scan a directory for files, returning (path, mime_type, file_size) tuples."""
    target = target.resolve()
    if not target.is_dir():
        raise ValueError(f"Not a directory: {target}")

    gitignore_spec = None
    git_root = None
    if not no_gitignore:
        git_root = find_git_root(start=target)
        if git_root:
            gitignore_spec = load_gitignore_specs(git_root=git_root, target=target)

    results: list[tuple[Path, str, int]] = []

    for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
        dirpath_path = Path(dirpath)

        dirnames[:] = [d for d in dirnames if not Path(dirpath_path / d).is_symlink()]

        for filename in sorted(filenames):
            file_path = dirpath_path / filename
            if file_path.is_symlink() and file_path.is_dir():
                continue

            if gitignore_spec and git_root:
                rel = file_path.relative_to(git_root)
                if gitignore_spec.match_file(str(rel)):
                    continue

            try:
                file_size = file_path.stat().st_size
            except OSError:
                continue

            if file_size > max_size:
                continue

            mime_type = detect_mime_type(path=file_path)

            if glob_pattern:
                if not file_path.match(glob_pattern):
                    continue

            if not include_binary and is_binary_mime(mime_type=mime_type):
                continue

            results.append((file_path, mime_type, file_size))

    return results
