"""Text utilities for truncation before sending to external LLMs / embedders."""
from __future__ import annotations

import re

MAX_EXTRACTOR_CHARS = 12_000      # ~3000 tokens for Russian, Claude extractor
MAX_EMBED_DOC_CHARS = 6_000       # ~1500 tokens, GigaChat doc chunk
MAX_EMBED_EXP_CHARS = 3_000       # ~750 tokens, GigaChat experience chunk
MAX_SCORER_VAC_CHARS = 8_000      # ~2000 tokens, vacancy block in Claude scorer
MAX_SCORER_RES_CHARS = 8_000      # ~2000 tokens, resume block in Claude scorer

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def truncate_by_sentence(text: str, max_chars: int) -> str:
    """Truncate text to <= max_chars, preferring sentence boundaries.

    Splits on sentence-ending punctuation or paragraph breaks, then re-joins
    pieces until adding the next would exceed max_chars. If no sentence fits,
    falls back to a hard slice.
    """
    if not text:
        return text
    if len(text) <= max_chars:
        return text

    pieces: list[str] = []
    used = 0
    for sentence in _SENTENCE_SPLIT.split(text):
        chunk = sentence.strip()
        if not chunk:
            continue
        if used + len(chunk) + 1 > max_chars:
            break
        pieces.append(chunk)
        used += len(chunk) + 1

    if pieces:
        return " ".join(pieces)
    return text[:max_chars]
