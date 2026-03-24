"""Async orchestrator: concurrency, retries, backoff, circuit breaker."""

from __future__ import annotations

import asyncio
import random

import httpx

from count_tokens.providers.base import FileResult, TokenCountResult, TokenCountProvider, UnsupportedFileTypeError
from count_tokens.scanner import validate_content_matches_mime


TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


async def count_file_tokens(
    *,
    provider: TokenCountProvider,
    file_result: FileResult,
    model: str,
    retries: int = 3,
) -> FileResult:
    try:
        content = file_result.path.read_bytes()
    except OSError as exc:
        file_result.status = "failed"
        file_result.error = str(exc)
        return file_result

    if not content:
        file_result.status = "success"
        file_result.token_count = TokenCountResult(total_tokens=0, model=model)
        return file_result

    mime_type = file_result.mime_type or "text/plain"

    if not validate_content_matches_mime(content=content, mime_type=mime_type):
        file_result.status = "skipped"
        file_result.skip_reason = f"File content does not match declared type {mime_type}"
        return file_result

    last_error = None
    for attempt in range(retries + 1):
        try:
            result = await provider.count_tokens(content=content, mime_type=mime_type, model=model)
            file_result.status = "success"
            file_result.token_count = result
            return file_result
        except UnsupportedFileTypeError as exc:
            file_result.status = "skipped"
            file_result.skip_reason = str(exc)
            return file_result
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code not in TRANSIENT_STATUS_CODES or attempt >= retries:
                file_result.status = "failed"
                file_result.error = f"HTTP {status_code}: {exc.response.text[:200]}"
                return file_result
            last_error = exc
            retry_after = exc.response.headers.get("retry-after")
            if retry_after:
                delay = float(retry_after)
            else:
                base_delay = min(2 ** attempt, 60)
                delay = base_delay * (0.5 + random.random())
            await asyncio.sleep(delay)
        except (httpx.RequestError, TimeoutError) as exc:
            if attempt >= retries:
                file_result.status = "failed"
                file_result.error = str(exc)
                return file_result
            last_error = exc
            base_delay = min(2 ** attempt, 60)
            delay = base_delay * (0.5 + random.random())
            await asyncio.sleep(delay)

    file_result.status = "failed"
    file_result.error = str(last_error) if last_error else "Unknown error"
    return file_result


async def run_token_counting(
    *,
    provider: TokenCountProvider,
    file_results: list[FileResult],
    model: str,
    concurrency: int = 10,
    retries: int = 3,
    progress_callback: callable | None = None,
) -> list[FileResult]:
    semaphore = asyncio.Semaphore(concurrency)
    consecutive_failures = 0
    circuit_broken = False

    async def process_file(file_result: FileResult) -> FileResult:
        nonlocal consecutive_failures, circuit_broken

        if circuit_broken:
            file_result.status = "failed"
            file_result.error = "Circuit breaker triggered — too many consecutive failures"
            return file_result

        async with semaphore:
            result = await count_file_tokens(
                provider=provider,
                file_result=file_result,
                model=model,
                retries=retries,
            )

            if result.status == "failed":
                consecutive_failures += 1
                if consecutive_failures >= 10:
                    circuit_broken = True
            elif result.status == "success":
                consecutive_failures = 0

            if progress_callback:
                progress_callback()

            return result

    tasks = [process_file(file_result=fr) for fr in file_results]
    return await asyncio.gather(*tasks)
