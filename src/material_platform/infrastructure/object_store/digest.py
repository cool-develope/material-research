from __future__ import annotations

import hashlib
from typing import BinaryIO

_CHUNK = 1024 * 1024


def sha256_stream(data: BinaryIO) -> tuple[str, int]:
    hasher = hashlib.sha256()
    total = 0
    while chunk := data.read(_CHUNK):
        hasher.update(chunk)
        total += len(chunk)
    return hasher.hexdigest(), total
