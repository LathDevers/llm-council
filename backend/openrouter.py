"""OpenRouter API client for making LLM requests."""

import asyncio
import random
from typing import Any

import httpx

from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

# Free-tier models share an upstream pool and return 429 intermittently; a short retry usually clears it.
MAX_ATTEMPTS = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_BACKOFF = 30.0


def _error_detail(response: httpx.Response) -> str:
    """Pull the human-readable reason out of an OpenRouter error body."""
    try:
        error = response.json()["error"]
    except Exception:
        return response.text[:500]

    message = error.get("message", "")
    # The top-level message is often just "Provider returned error"; the upstream
    # provider's actual explanation lives in metadata.raw.
    raw = error.get("metadata", {}).get("raw")
    if raw and raw not in message:
        return f"{message} ({raw})"
    return message or response.text[:500]


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying, preferring whatever the server told us."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return min(float(header), MAX_BACKOFF)
        except ValueError:
            pass

    try:
        hinted = response.json()["error"]["metadata"]["retry_after_seconds"]
        return min(float(hinted), MAX_BACKOFF)
    except Exception:
        pass

    # Exponential backoff with jitter so 15 parallel models don't retry in lockstep.
    return min(2.0**attempt + random.uniform(0, 1), MAX_BACKOFF)


async def query_model(model: str, messages: list[dict[str, str]], timeout: float = 120.0) -> dict[str, Any] | None:
    """
    Query a single model via OpenRouter API.

    Retries transient failures (rate limits, upstream 5xx) up to MAX_ATTEMPTS times.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: list of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    for attempt in range(MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                response.raise_for_status()

                data = response.json()
                message = data["choices"][0]["message"]

                return {"content": message.get("content"), "reasoning_details": message.get("reasoning_details")}

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            detail = _error_detail(e.response)
            last_attempt = attempt == MAX_ATTEMPTS - 1

            if status in RETRY_STATUS_CODES and not last_attempt:
                delay = _retry_delay(e.response, attempt)
                print(f"Retrying model {model} in {delay:.1f}s: HTTP {status} - {detail}")
                await asyncio.sleep(delay)
                continue

            print(f"Error querying model {model}: HTTP {status} - {detail}")
            return None

        except Exception as e:
            print(f"Error querying model {model}: {type(e).__name__}: {e}")
            return None

    return None


async def query_models_parallel(models: list[str], messages: list[dict[str, str]]) -> dict[str, dict[str, Any] | None]:
    """
    Query multiple models in parallel.

    Args:
        models: list of OpenRouter model identifiers
        messages: list of message dicts to send to each model

    Returns:
        dict mapping model identifier to response dict (or None if failed)
    """
    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
