# Material Platform

Turn a folder of research zips into **searchable, citable materials**, then ask questions with **Deep Research** that cites pages and source lines — not a chatty summary of the whole dump.

A zip is a container. Discovery splits it into independent materials (paper, project tree, dataset, wheel). Process extracts units (PDF page, code symbol, table), embeds them, and indexes them. Search returns materials. The agent retrieves units and writes a cited report.

## Where it fits

| You have | You use this for |
| --- | --- |
| Mixed research drops (PDF + code + CSV in one zip) | Ingest once, search and ask later |
| A lab / team inbox of archives | Dagster: one job per zip, one job per material |
| An internal knowledge desk | Hop-1 search UI + signed-in Deep Research chat |
| A private corpus you do not want to upload as raw zips | Keep the zip on your disk or FTP share; store only materials and extracts |

It is a **local or self-hosted** stack (your Postgres, MinIO, Qdrant, optional vLLM). It is not a hosted SaaS in this repo, not a generic web crawler, and not a replacement for reading the primary sources.

## How you use it

**1. Laptop, no Docker** — try the sample zip:

```bash
uv sync --group dev
uv run pytest
uv run mp ingest tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-simple --process
uv run mp search "handle_request" --data-dir /tmp/mp-simple
uv run mp chat "handle_request" --data-dir /tmp/mp-simple
```

That zip is three materials: `paper.pdf`, `backend/`, `dataset/`.

**2. Compose stack** — identities in Postgres, bytes in MinIO, vectors in Qdrant, UI + Dagster:

```bash
cp .env.example .env
mkdir -p inbox
docker compose up -d --build
uv run alembic upgrade head
```

- Search / chat API: `uv run mp serve --postgres` and `cd web && npm install && npm run dev` → [http://localhost:5173](http://localhost:5173)
- Dagster: [http://localhost:3000](http://localhost:3000) — turn on both sensors, drop finished zips into `inbox/`
- Langfuse (optional traces): [http://localhost:3100](http://localhost:3100)

Search is public. Deep Research needs sign-in. Citations look like `paper.pdf page 1` or `src/api.py lines 1-2`.

**3. Your own models** — analysis and chat already call `LLM_BASE_URL` (Ollama, vLLM, any OpenAI-compatible server). Embed / rerank are local BGE today or `EMBEDDER=http` / `RERANKER=http` when you have those APIs.

Python 3.12, uv. Node 22+ for the web UI. Details: [docs/setup.md](docs/setup.md), [docs/environment.md](docs/environment.md).

## What happens to a zip

```text
inbox zip  →  Discovery (materials)  →  extract + analyze  →  Qdrant
                                         cited units              │
                                         material card ───────────┘
                                              │
                         search (hop 1)   or   Deep Research (hop 1 + 2)
```

The archive stays on the inbox. We keep material bytes, extract JSON, pipeline status, and vectors. See [docs/pipeline.md](docs/pipeline.md) and [docs/agent.md](docs/agent.md).

## Docs

| Doc | Topic |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | Layers and request paths |
| [docs/system-design.md](docs/system-design.md) | Ingest, process, search, chat, auth |
| [docs/pipeline.md](docs/pipeline.md) | What we extract and how it is indexed |
| [docs/agent.md](docs/agent.md) | Deep Research graph and evidence |
| [docs/setup.md](docs/setup.md) | Local and compose spin-up |
| [docs/environment.md](docs/environment.md) | Env vars |
| [docs/dagster.md](docs/dagster.md) | Jobs, sensors, compose UI |
| [docs/inbox.md](docs/inbox.md) | Source drop and what we do not keep |
| [docs/inference.md](docs/inference.md) | Local BGE vs HTTP embed / rerank |
| [docs/structure.md](docs/structure.md) | Packages and files |
| [docs/todos.md](docs/todos.md) | Open follow-ups |
| [docs/airgap.md](docs/airgap.md) | Offline install bundle |

## License

Copyright (C) 2026 Cool Developer.

This program is free software under the [GNU Affero General Public License v3.0](LICENSE) only. You may run it, study it, and share it. If you modify it and let others use it over a network (including a hosted Deep Research service), you must offer them the corresponding source.

You can charge for support, hosting, or a separate commercial license. For paid closed-source use, contact `cool199966@outlook.com`.
