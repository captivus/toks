"""xAI Grok token counting provider.

Text: counted via /v1/tokenize-text API endpoint.
Images (JPEG, PNG): counted locally using xAI's documented tiling formula.
  Source: https://docs.x.ai/docs/key-information/consumption-and-rate-limits
  Formula: images are broken into 448x448 pixel tiles, each tile = 256 tokens,
  plus one extra tile. Max 6 tiles = 1,792 tokens.
PDFs: not supported (xAI uses server-side tool, no token counting available).
"""

import io
import math
import struct

import httpx

from toks.providers.base import TokenCountResult, UnsupportedFileTypeError

NON_TEXT_SUPPORTED = {"application/json", "application/xml"}
IMAGE_SUPPORTED = {"image/jpeg", "image/png"}
TILE_SIZE = 448
TOKENS_PER_TILE = 256
MAX_TILES = 6


def _get_image_dimensions(*, content: bytes, mime_type: str) -> tuple[int, int] | None:
    """Extract width and height from JPEG or PNG without external dependencies."""
    if mime_type == "image/png" and content[:4] == b"\x89PNG":
        if len(content) >= 24:
            width = struct.unpack(">I", content[16:20])[0]
            height = struct.unpack(">I", content[20:24])[0]
            return (width, height)
    elif mime_type == "image/jpeg" and content[:2] == b"\xff\xd8":
        offset = 2
        while offset < len(content) - 1:
            marker = content[offset:offset + 2]
            if marker[0:1] != b"\xff":
                break
            if marker[1:2] in (b"\xc0", b"\xc1", b"\xc2"):
                if offset + 9 < len(content):
                    height = struct.unpack(">H", content[offset + 5:offset + 7])[0]
                    width = struct.unpack(">H", content[offset + 7:offset + 9])[0]
                    return (width, height)
            if marker[1:2] == b"\xd9":
                break
            if offset + 3 < len(content):
                length = struct.unpack(">H", content[offset + 2:offset + 4])[0]
                offset += 2 + length
            else:
                break
    return None


def _calculate_image_tokens(*, width: int, height: int) -> int:
    """Calculate Grok image tokens using xAI's documented tiling formula.

    Source: https://docs.x.ai/docs/key-information/consumption-and-rate-limits
    Images are broken into 448x448 tiles, each tile = 256 tokens, +1 extra tile.
    """
    tiles_x = math.ceil(width / TILE_SIZE)
    tiles_y = math.ceil(height / TILE_SIZE)
    num_tiles = min(tiles_x * tiles_y, MAX_TILES)
    return (num_tiles + 1) * TOKENS_PER_TILE


class GrokProvider:
    provider_name = "grok"

    def __init__(self, *, api_key: str):
        self._api_key = api_key

    def supported_mime_types(self) -> set[str]:
        return NON_TEXT_SUPPORTED | IMAGE_SUPPORTED | {"text/*"}

    async def count_tokens(self, *, content: bytes, mime_type: str, model: str) -> TokenCountResult:
        if not content:
            return TokenCountResult(total_tokens=0, model=model)

        if mime_type in IMAGE_SUPPORTED:
            return self._count_image_tokens(content=content, mime_type=mime_type, model=model)

        if not (mime_type.startswith("text/") or mime_type in NON_TEXT_SUPPORTED):
            raise UnsupportedFileTypeError(mime_type=mime_type, provider=self.provider_name)

        text = content.decode(errors="replace")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.x.ai/v1/tokenize-text",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": model, "text": text},
                timeout=120.0,
            )
            response.raise_for_status()
            token_ids = response.json()["token_ids"]
            return TokenCountResult(total_tokens=len(token_ids), model=model)

    def _count_image_tokens(self, *, content: bytes, mime_type: str, model: str) -> TokenCountResult:
        dimensions = _get_image_dimensions(content=content, mime_type=mime_type)
        if dimensions is None:
            raise UnsupportedFileTypeError(mime_type=mime_type, provider=self.provider_name)
        width, height = dimensions
        tokens = _calculate_image_tokens(width=width, height=height)
        return TokenCountResult(total_tokens=tokens, model=model)
