"""Google Gemini token counting provider."""

import base64

import httpx

from count_tokens.providers.base import TokenCountResult, UnsupportedFileTypeError

NON_TEXT_SUPPORTED = {
    "application/json", "application/xml", "application/javascript",
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/heic", "image/heif", "image/bmp", "image/tiff", "image/svg+xml",
    "application/pdf",
}


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, *, api_key: str):
        self._api_key = api_key

    def supported_mime_types(self) -> set[str]:
        return NON_TEXT_SUPPORTED | {"text/*"}

    def _is_supported(self, *, mime_type: str) -> bool:
        return mime_type.startswith("text/") or mime_type in NON_TEXT_SUPPORTED

    async def count_tokens(self, *, content: bytes, mime_type: str, model: str) -> TokenCountResult:
        if not content:
            return TokenCountResult(total_tokens=0, model=model)
        if not self._is_supported(mime_type=mime_type):
            raise UnsupportedFileTypeError(mime_type=mime_type, provider=self.provider_name)

        if mime_type.startswith("text/") or mime_type in ("application/json", "application/xml", "application/javascript"):
            parts = [{"text": content.decode(errors="replace")}]
        else:
            parts = [{"inline_data": {"mime_type": mime_type, "data": base64.b64encode(content).decode()}}]

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:countTokens"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params={"key": self._api_key},
                json={"contents": [{"parts": parts}]},
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            total = data.get("totalTokens", 0)
            breakdown = None
            if "promptTokensDetails" in data:
                breakdown = {d["modality"]: d["tokenCount"] for d in data["promptTokensDetails"]}
            return TokenCountResult(total_tokens=total, model=model, modality_breakdown=breakdown)
