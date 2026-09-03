# Material Platform

Discover independent research materials from files, directories, and ZIP archives, then process each one into a `ResearchMaterial` for search and Deep Research.

Python 3.12, uv. Postgres owns identities; the object store owns bytes; Discovery owns Material boundaries; Qdrant owns retrieval; Dagster is optional.

## Docs

| Doc | Topic |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | Layers and request paths |
| [docs/system-design.md](docs/system-design.md) | Ingest, process, search, chat, auth |
| [docs/pipeline.md](docs/pipeline.md) | What we extract and how it is indexed |
| [docs/agent.md](docs/agent.md) | Deep Research graph and evidence |
| [docs/structure.md](docs/structure.md) | Packages, services, files |
| [docs/setup.md](docs/setup.md) | Local and compose spin-up |
| [docs/environment.md](docs/environment.md) | Env vars and how they relate |
| [docs/dagster.md](docs/dagster.md) | Jobs, sensors, inbox folder, pools |
| [docs/inbox.md](docs/inbox.md) | Source drop and first run |
| [docs/inference.md](docs/inference.md) | Local BGE vs HTTP embed / rerank |
| [docs/todos.md](docs/todos.md) | Open follow-ups |

## Quick start

```bash
uv sync --group dev
uv run pytest
uv run mp ingest tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-simple --process
uv run mp search "handle_request" --data-dir /tmp/mp-simple
```

Copy `.env.example` to `.env` before Postgres, MinIO, or Langfuse. App UI: `mp serve` + `cd web && npm run dev` — see [docs/setup.md](docs/setup.md).
