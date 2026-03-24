"""Base types, protocols, and exceptions for providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol


class UnsupportedFileTypeError(Exception):
    def __init__(self, *, mime_type: str, provider: str):
        self.mime_type = mime_type
        self.provider = provider
        super().__init__(f"{mime_type} not supported by {provider}")


@dataclass
class TokenCountResult:
    total_tokens: int
    model: str
    modality_breakdown: dict[str, int] | None = None


@dataclass
class FileResult:
    path: Path
    mime_type: str | None
    file_size: int
    status: Literal["pending", "success", "failed", "skipped"] = "pending"
    token_count: TokenCountResult | None = None
    error: str | None = None
    skip_reason: str | None = None


@dataclass
class ModelInfo:
    model_id: str
    provider: str
    max_input_tokens: int
    max_output_tokens: int | None = None


@dataclass
class ProviderConfig:
    api_key: str
    model: str
    agent_model: str | None = None
    plan: str = "free"
    has_coding_agent: bool = False


@dataclass
class Config:
    default_provider: str
    providers: dict[str, ProviderConfig] = field(default_factory=dict)


@dataclass
class RunResult:
    results: list[FileResult]
    tree: dict
    provider: str
    model: str


class TokenCountProvider(Protocol):
    provider_name: str

    def supported_mime_types(self) -> set[str]: ...

    async def count_tokens(self, *, content: bytes, mime_type: str, model: str) -> TokenCountResult: ...
