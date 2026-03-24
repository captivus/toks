"""xAI Grok token counting provider."""

import httpx

from count_tokens.providers.base import TokenCountResult, UnsupportedFileTypeError

NON_TEXT_SUPPORTED = {"application/json", "application/xml"}


class GrokProvider:
    provider_name = "grok"

    def __init__(self, *, api_key: str):
        self._api_key = api_key

    def supported_mime_types(self) -> set[str]:
        return NON_TEXT_SUPPORTED | {"text/*"}

    async def count_tokens(self, *, content: bytes, mime_type: str, model: str) -> TokenCountResult:
        if not content:
            return TokenCountResult(total_tokens=0, model=model)
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
