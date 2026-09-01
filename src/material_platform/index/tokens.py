from __future__ import annotations

import re

TOKEN = re.compile(r"[a-z0-9_]{2,}")
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
