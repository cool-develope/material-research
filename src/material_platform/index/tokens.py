from __future__ import annotations

import hashlib
import math
import re

TOKEN = re.compile(r"[a-z0-9_]{2,}")
EMBED_DIM = 64
_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "to",
        "and",
        "or",
        "in",
        "on",
        "for",
        "is",
        "it",
        "as",
        "at",
        "by",
        "be",
    }
)


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(token for token in TOKEN.findall(text.lower()) if token not in _STOP)


def embed(tokens: tuple[str, ...]) -> tuple[float, ...]:
    vector = [0.0] * EMBED_DIM
    for token in tokens:
        digest = hashlib.sha256(token.encode()).hexdigest()[:8]
        vector[int(digest, 16) % EMBED_DIM] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return tuple(vector)
    return tuple(value / norm for value in vector)


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def lexical_score(query: tuple[str, ...], document: tuple[str, ...]) -> float:
    if not query:
        return 0.0
    present = set(document)
    hits = sum(1 for token in query if token in present)
    return hits / len(query)


def combined_score(
    query_tokens: tuple[str, ...],
    query_vector: tuple[float, ...],
    document_tokens: tuple[str, ...],
    document_vector: tuple[float, ...],
) -> float:
    lexical = lexical_score(query_tokens, document_tokens)
    vector = cosine(query_vector, document_vector)
    return 0.6 * lexical + 0.4 * vector
