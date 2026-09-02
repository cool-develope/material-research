from __future__ import annotations

from material_platform.extraction.tokens import tokenize

DEFAULT_CHUNK_TOKENS = 512
DEFAULT_CHUNK_OVERLAP = 64
_WRAP_TOKENS = 16


def token_count(text: str) -> int:
    return len(tokenize(text))


def window_text(text: str, *, size: int, overlap: int) -> tuple[str, ...]:
    return tuple(span[0] for span in window_spans(text, size=size, overlap=overlap))


def window_spans(
    text: str, *, size: int, overlap: int
) -> tuple[tuple[str, int, int], ...]:
    if not text:
        return (("", 1, 1),)
    size = max(size, 1)
    overlap = min(max(overlap, 0), size - 1)
    pieces = _pieces(text, size)
    return _pack(pieces, size=size, overlap=overlap)


def _pieces(text: str, size: int) -> list[tuple[str, int, int]]:
    lines = text.splitlines()
    if not lines:
        return [(text, 1, 1)]
    wrap = min(_WRAP_TOKENS, size)
    pieces: list[tuple[str, int, int]] = []
    line_no = 1
    for line in lines:
        if token_count(line) <= size:
            pieces.append((line, line_no, line_no))
            line_no += 1
            continue
        for part in _split_line(line, wrap):
            pieces.append((part, line_no, line_no))
            line_no += 1
    return pieces


def _split_line(line: str, size: int) -> list[str]:
    words = line.split()
    if not words:
        return [line]
    parts: list[str] = []
    current: list[str] = []
    used = 0
    for word in words:
        extra = token_count(word)
        if current and used + extra > size:
            parts.append(" ".join(current))
            current = [word]
            used = extra
            continue
        current.append(word)
        used += extra
    if current:
        parts.append(" ".join(current))
    return parts


def _pack(
    pieces: list[tuple[str, int, int]],
    *,
    size: int,
    overlap: int,
) -> tuple[tuple[str, int, int], ...]:
    total = len(pieces)
    index = 0
    windows: list[tuple[str, int, int]] = []
    while index < total:
        used = 0
        end = index
        while end < total:
            extra = token_count(pieces[end][0])
            if end > index and used + extra > size:
                break
            used += extra
            end += 1
        if end == index:
            end = index + 1
            used = token_count(pieces[index][0])
        content = "\n".join(item[0] for item in pieces[index:end])
        windows.append((content, pieces[index][1], pieces[end - 1][2]))
        if end >= total:
            break
        skip_target = max(used - overlap, 1)
        skipped = 0
        next_index = index
        while next_index < end and skipped < skip_target:
            skipped += token_count(pieces[next_index][0])
            next_index += 1
        index = max(next_index, index + 1)
    return tuple(windows)
