"""Anthropic Claude token counting provider."""

import base64

import httpx

from toks.providers.base import TokenCountResult, UnsupportedFileTypeError

NON_TEXT_SUPPORTED = {
    "application/json", "application/xml",
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
}


class ClaudeProvider:
    provider_name = "claude"

    def __init__(self, *, api_key: str):
        self._api_key = api_key

    def supported_mime_types(self) -> set[str]:
        return NON_TEXT_SUPPORTED | {"text/*"}

    async def count_tokens(self, *, content: bytes, mime_type: str, model: str) -> TokenCountResult:
        if not content:
            return TokenCountResult(total_tokens=0, model=model)
        if not (mime_type.startswith("text/") or mime_type in NON_TEXT_SUPPORTED):
            raise UnsupportedFileTypeError(mime_type=mime_type, provider=self.provider_name)

        if mime_type.startswith("image/"):
            content_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": base64.b64encode(content).decode()},
            }
        elif mime_type == "application/pdf":
            content_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": mime_type, "data": base64.b64encode(content).decode()},
            }
        else:
            content_block = {"type": "text", "text": content.decode(errors="replace")}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages/count_tokens",
                headers={"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": [content_block]}]},
                timeout=120.0,
            )
            response.raise_for_status()
            return TokenCountResult(total_tokens=response.json()["input_tokens"], model=model)
