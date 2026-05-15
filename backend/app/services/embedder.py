"""GigaChat embeddings client.

Wraps the synchronous `gigachat` SDK in an async-friendly interface,
adds tenacity-retry, and exposes a single `embed_batch` method that
returns one vector per input text in the same order.
"""
from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from gigachat import GigaChat
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbedderError(Exception):
    """Raised when embeddings cannot be obtained from GigaChat."""


class GigaChatEmbedder:
    """Async wrapper around the synchronous `gigachat` SDK."""

    def __init__(
        self,
        credentials: str,
        scope: str = "GIGACHAT_API_PERS",
        model: str = "Embeddings",
        verify_ssl_certs: bool = False,
    ) -> None:
        if not credentials:
            raise EmbedderError("GIGACHAT_CREDENTIALS is empty")
        self._client = GigaChat(
            credentials=credentials,
            scope=scope,
            model=model,
            verify_ssl_certs=verify_ssl_certs,
        )
        self._model = model

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings(texts=texts)
        return [item.embedding for item in response.data]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, preserving order.

        Raises EmbedderError if the SDK call fails after retries.
        """
        if not texts:
            return []
        try:
            return await asyncio.to_thread(self._embed_sync, texts)
        except Exception as exc:
            logger.warning("gigachat embed_batch failed after retries: %s", exc)
            raise EmbedderError(str(exc)) from exc


@lru_cache
def get_embedder() -> GigaChatEmbedder:
    settings = get_settings()
    return GigaChatEmbedder(
        credentials=settings.GIGACHAT_CREDENTIALS,
        scope=settings.GIGACHAT_SCOPE,
        model=settings.GIGACHAT_MODEL,
        verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
    )
