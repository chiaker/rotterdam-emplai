"""Anthropic Claude client wrapper.

Thin async wrapper around the official Anthropic SDK with:
- Lazy client construction (no import-time API key check).
- Helper to build cache-controlled system blocks (up to 4 breakpoints supported).
- Tenacity-retry on transient errors only (429 / 5xx / timeout / connection),
  with non-retryable errors (400 / 401 / 403 / 404) surfaced immediately as ClaudeError.
- Forced tool_use call that returns the tool's input dict.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import Message, ToolUseBlock
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ClaudeError(Exception):
    """Raised when a Claude API call fails non-retryably or all retries are exhausted."""


def text_block(text: str, cache: bool = False) -> dict[str, Any]:
    """Build a text content block, optionally marked for ephemeral caching."""
    block: dict[str, Any] = {"type": "text", "text": text}
    if cache:
        block["cache_control"] = {"type": "ephemeral"}
    return block


@lru_cache
def _build_client(api_key: str) -> AsyncAnthropic:
    return AsyncAnthropic(api_key=api_key)


def get_client() -> AsyncAnthropic:
    """Return a cached AsyncAnthropic client. Raises ClaudeError if no API key set."""
    settings = get_settings()
    if not settings.ANTHROPIC_API_KEY:
        raise ClaudeError("ANTHROPIC_API_KEY is empty")
    return _build_client(settings.ANTHROPIC_API_KEY)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
        ),
    ):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500
    return False


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_retryable),
)
async def call_tool_use(
    *,
    system_blocks: list[dict[str, Any]],
    user_content: str | list[dict[str, Any]],
    tool: dict[str, Any],
    max_tokens: int = 1024,
    thinking: dict[str, Any] | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    """Call Claude forcing a single tool_use; return the tool's `input` dict.

    Args:
        system_blocks: multi-block system prompt (text blocks, optionally with
            cache_control). Render order is tools → system → messages, so put
            stable content first and per-request content last.
        user_content: user message text or pre-built content blocks.
        tool: tool definition with name / description / input_schema.
        max_tokens: cap on Claude's output tokens.
        thinking: optional thinking config, e.g. {"type": "adaptive"}.
        effort: optional effort level inside output_config (low/medium/high/max).

    Returns:
        The tool_use block's `input` as a plain dict.

    Raises:
        ClaudeError on non-retryable errors (4xx) or after retries are exhausted.
    """
    settings = get_settings()
    client = get_client()

    kwargs: dict[str, Any] = {
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": system_blocks,
        "tools": [tool],
        "tool_choice": {"type": "tool", "name": tool["name"]},
        "messages": [{"role": "user", "content": user_content}],
    }
    if thinking is not None:
        kwargs["thinking"] = thinking
    if effort is not None:
        kwargs["output_config"] = {"effort": effort}

    try:
        response: Message = await client.messages.create(**kwargs)
    except (
        anthropic.BadRequestError,
        anthropic.AuthenticationError,
        anthropic.PermissionDeniedError,
        anthropic.NotFoundError,
    ) as exc:
        raise ClaudeError(f"{type(exc).__name__}: {str(exc)[:200]}") from exc

    for block in response.content:
        if isinstance(block, ToolUseBlock) and block.name == tool["name"]:
            return dict(block.input)

    raise ClaudeError(
        f"no tool_use block in response (stop_reason={response.stop_reason})"
    )
