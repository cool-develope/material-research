# Material Platform

Discover independent research materials from files, directories, and ZIP archives, then process each one into a `ResearchMaterial` for Deep Research.

## Setup

Python 3.12, managed with uv:

```bash
uv sync --group dev
```

That creates `.venv`, installs dependencies, and installs this package in editable mode.

```bash
source .venv/bin/activate   # optional; `uv run` is enough
uv run pytest
```

Copy `.env.example` to `.env` when you start using Postgres and MinIO.
