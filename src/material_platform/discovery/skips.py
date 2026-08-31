IGNORE_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__MACOSX",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)

JUNK_FILE_NAMES = frozenset({".DS_Store", "Thumbs.db"})


def is_skipped_name(name: str) -> bool:
    return name in IGNORE_DIR_NAMES or name in JUNK_FILE_NAMES or name.startswith(".")
