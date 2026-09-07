# Setup

Python 3.12, managed with uv. Node 22+ for the UI (`npm`; do not `apt install npm`).

```bash
uv sync --group dev
uv run pytest
```

Pytest ignores `.env` and pins `EMBEDDER=fake`, `RERANKER=off`, `ANALYZER=deterministic`.

Copy `.env.example` to `.env` before Postgres, MinIO, or Langfuse. See [Environment](environment.md).

## Local sqlite (no Docker)

```bash
uv run mp ingest tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-simple --process
uv run mp search "handle_request" --data-dir /tmp/mp-simple
uv run mp chat "handle_request" --data-dir /tmp/mp-simple --trace
```

Use a **fresh `--data-dir`** per ingest. That zip is three materials (`paper.pdf`, `backend/`, `dataset/`).

## Compose (Postgres, MinIO, Qdrant, Redis, Langfuse)

```bash
docker compose up -d
uv run alembic upgrade head
```

Langfuse UI: [http://localhost:3100](http://localhost:3100) — `langfuse@example.com` / `langfuselocal`. Keys in `.env.example` match compose (`pk-lf-local` / `sk-lf-local`).

```bash
uv run mp ingest tests/fixtures/simple_mix/research.zip \
  --postgres --process
uv run mp search "handle_request" --postgres
uv run mp serve --postgres
```

`--postgres` uses `DATABASE_URL`, MinIO, and Qdrant. Match `QDRANT_COLLECTION` and `EMBEDDER` to the ingest.

## BGE embedder + reranker

Weights are not in git:

```bash
uv pip install huggingface_hub
uv run python scripts/download_bge.py
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install FlagEmbedding
```

Then ingest with `EMBEDDER=bge-m3`. Hop-2 rerank is `RERANKER=bge-v2-m3`.

## App (search + Deep Research)

AIML zip is gitignored. Build once, then ingest to collection `research_aiml`:

```bash
uv run mp eval-aiml --build-only
docker compose up -d
uv run mp eval-aiml --skip-build --prod --data-dir /tmp/mp-aiml-prod
```

Two terminals:

```bash
EMBEDDER=bge-m3 RERANKER=bge-v2-m3 QDRANT_COLLECTION=research_aiml \
  uv run mp serve --postgres
```

```bash
export PATH="$HOME/.local/node/bin:$PATH"   # if npm is not on PATH
cd web && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Search is public. Research redirects to `/signin`. After sign-in, `/chat` continues a thread in the URL.

## LLM analysis / agent

Needs `LLM_BASE_URL` (Ollama or any OpenAI-compatible server):

```bash
ANALYZER=llm \
LLM_BASE_URL=http://127.0.0.1:11434/v1 \
LLM_API_KEY=ollama \
LLM_MODEL=llama3.1 \
uv run mp ingest tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-llm --process
```

`mp chat --llm` uses the same URL. Chat on `mp serve` uses it when set.

## Dagster

Compose runs the UI and daemon (sensors). Inbox is `./inbox` on the host, `/inbox` in the container.

```bash
mkdir -p inbox
docker compose up -d --build
uv run alembic upgrade head
```

UI: [http://127.0.0.1:3000](http://127.0.0.1:3000). Turn on `ingest_directory_sensor` and `pending_materials_sensor`. Drop a finished zip into `inbox/`.

The image talks to Postgres / MinIO / Qdrant on the compose network. It does not install FlagEmbedding; use `EMBEDDER=http` / `RERANKER=http` in `.env` for process jobs inside the container.

Host `dagster dev` is optional debug (do not bind port 3000 at the same time):

```bash
mkdir -p .dagster inbox
cp dagster.yaml .dagster/dagster.yaml
export DAGSTER_HOME="$(pwd)/.dagster"
export INGEST_DIRECTORY="$(pwd)/inbox"
uv run dagster dev -w workspace.yaml
```

Config: [Dagster](dagster.md). First run: [Inbox](inbox.md). Air-gap USB bundle: [Air-gap](airgap.md).

## Eval

```bash
uv run mp eval --data-dir /tmp/mp-simple --lexical-only
uv run mp eval-aiml --skip-build --prod --data-dir /tmp/mp-aiml-prod
```

`--lexical-only` is the cheap gate (fake embedder, no reranker). `--prod` uses compose + BGE + reranker + LLM and writes `{data-dir}/eval_aiml_report.txt`.

End-to-end against compose:

```bash
uv run python scripts/e2e_research.py
LIVE_COMPOSE=1 uv run pytest tests/integration/test_compose_reingest.py
```
