"""OpenAI token counting provider."""

import base64

import httpx

from count_tokens.providers.base import TokenCountResult, UnsupportedFileTypeError

NON_TEXT_SUPPORTED = {
    "application/json", "application/xml",
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

MIME_TO_EXTENSION = {
    "application/pdf": "document.pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document.docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document.xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "document.pptx",
}


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, *, api_key: str):
        self._api_key = api_key

    def supported_mime_types(self) -> set[str]:
        return NON_TEXT_SUPPORTED | {"text/*"}

    async def count_tokens(self, *, content: bytes, mime_type: str, model: str) -> TokenCountResult:
        if not content:
            return TokenCountResult(total_tokens=0, model=model)
        if not (mime_type.startswith("text/") or mime_type in NON_TEXT_SUPPORTED):
            raise UnsupportedFileTypeError(mime_type=mime_type, provider=self.provider_name)

        b64 = base64.b64encode(content).decode()

        if mime_type.startswith("image/"):
            input_payload = [{"role": "user", "content": [
                {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"},
            ]}]
        elif mime_type.startswith("text/") or mime_type in ("application/json", "application/xml"):
            input_payload = content.decode(errors="replace")
        else:
            filename = MIME_TO_EXTENSION.get(mime_type, "document.bin")
            input_payload = [{"role": "user", "content": [
                {"type": "input_file", "filename": filename, "file_data": f"data:{mime_type};base64,{b64}"},
            ]}]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/responses/input_tokens",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": model, "input": input_payload},
                timeout=120.0,
            )
            response.raise_for_status()
            return TokenCountResult(total_tokens=response.json()["input_tokens"], model=model)
