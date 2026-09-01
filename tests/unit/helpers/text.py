from material_platform.index.tokens import tokenize


def numbered_words(count: int, prefix: str, *, per_line: int = 16) -> str:
    words = [f"{prefix}{index:05d}" for index in range(count)]
    lines = [
        " ".join(words[index : index + per_line])
        for index in range(0, count, per_line)
    ]
    return "\n".join(lines) + "\n"


def word_count(text: str) -> int:
    return len(tokenize(text))
