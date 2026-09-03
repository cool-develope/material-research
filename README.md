# Material Platform

Discover independent research materials from files, directories, and ZIP archives, then process each one into a `ResearchMaterial` for Deep Research.

Python 3.12, managed with uv. PostgreSQL owns identities and state; the object store owns bytes; the Discovery Engine owns Material boundaries; Dagster owns execution.

## Setup

```bash
uv sync --group dev
uv run pytest
```

Pytest ignores `.env` and pins `EMBEDDER=fake`, `RERANKER=off`, `ANALYZER=deterministic`. Copy `.env.example` to `.env` when you start using Postgres and MinIO. `scripts/e2e_research.py` and `mp eval-aiml --prod` force BGE + reranker + LLM on top of that file.

BGE weights (embed + reranker) are not in git. Download them into the Hugging Face cache:

```bash
uv pip install huggingface_hub
uv run python scripts/download_bge.py
```

That caches `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3`. Search still uses Qdrant hybrid RRF; the reranker is on disk for later.

Install CPU inference (torch is not in the default lockfile):

```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install FlagEmbedding
```

Then ingest with BGE-M3 instead of the hashed fake embedder:

```bash
EMBEDDER=bge-m3 uv run mp ingest \
  tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-bge --process
EMBEDDER=bge-m3 uv run mp search "handle_request" \
  --data-dir /tmp/mp-bge
EMBEDDER=bge-m3 uv run mp eval --data-dir /tmp/mp-bge
```

Harder ranking eval (eight Materials). After the same BGE ingest, the reranker is opt-in:

```bash
EMBEDDER=bge-m3 uv run mp ingest \
  tests/fixtures/eval_hard/research.zip \
  --data-dir /tmp/mp-eval-hard-bge --process
EMBEDDER=bge-m3 uv run mp eval \
  --data-dir /tmp/mp-eval-hard-bge --cases tests/fixtures/eval/eval_hard.json
EMBEDDER=bge-m3 RERANKER=bge-v2-m3 uv run mp eval \
  --data-dir /tmp/mp-eval-hard-bge --cases tests/fixtures/eval/eval_hard.json
```

LLM analysis is one `MaterialAnalysis` per Material. Small materials are analyzed directly; long documents are reduced hierarchically; projects are inventoried then deep-read (20 files); artifacts use package metadata. Retrieval chunks stay 512/64. Default analyzer is deterministic. For Ollama or any OpenAI-compatible server:

```bash
ANALYZER=llm \
LLM_BASE_URL=http://127.0.0.1:11434/v1 \
LLM_API_KEY=ollama \
LLM_MODEL=llama3.1 \
uv run mp ingest tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-llm --process
```

## Local ingest (no Dagster)

SQLite + filesystem store, no Docker:

```bash
uv run mp ingest tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-simple --process
uv run mp search "Introduction to materials" \
  --data-dir /tmp/mp-simple
uv run mp search "handle_request" \
  --data-dir /tmp/mp-simple
uv run mp search "handle_request" \
  --data-dir /tmp/mp-simple --material-type project
uv run mp chat "handle_request" \
  --data-dir /tmp/mp-simple --trace
uv run mp chat "handle_request" \
  --data-dir /tmp/mp-simple --mode quick
uv run mp chat "where is it defined" \
  --data-dir /tmp/mp-simple --thread-id THREAD
uv run mp eval --data-dir /tmp/mp-simple --lexical-only
uv run mp eval \
  --source tests/fixtures/eval_long/research.zip \
  --cases tests/fixtures/eval/eval_long.json \
  --sweep chunk_tokens=256,512,1024 \
  --work-dir /tmp/mp-chunk-sweep \
  --lexical-only
```

That zip is three Materials (`paper.pdf`, `backend/`, `dataset/`). Use a **fresh `--data-dir`** per ingest so older sources are not mixed into sibling lists.

## App (search + Deep Research)

The UI talks to `mp serve`. Use the public AI/ML corpus (SLP3, QLoRA/LoRA/ReAct papers, Hugging Face trees, Alpaca CSV, DJL JAR) — not the three-file simple mix. The zip is gitignored; it is already built at `tests/fixtures/eval_aiml/research.zip` after `mp eval-aiml --build-only`.

`--data-dir` is a local sqlite path (embedded Qdrant + files on disk). The app stack is compose: Postgres identities, MinIO bytes, Qdrant retrieval. `docker compose up -d` first. AIML prod ingest writes collection `research_aiml` (BGE-M3); do not query it with the hashed fake embedder.

```bash
# Once, if the zip is missing:
uv run mp eval-aiml --build-only

# Once, if Qdrant collection research_aiml is empty:
uv run mp eval-aiml --skip-build --prod --data-dir /tmp/mp-aiml-prod
```

Two terminals:

```bash
EMBEDDER=bge-m3 RERANKER=bge-v2-m3 QDRANT_COLLECTION=research_aiml \
  uv run mp serve --postgres
```

Need Node 22+ (`npm`). Do not `apt install npm`. If `npm` is missing, put a local Node on `PATH` (this machine already has v22 at `~/.local/node`):

```bash
export PATH="$HOME/.local/node/bin:$PATH"
cd web && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Search is hop-1 material cards (`Speech and Language Processing`, `4-bit NormalFloat`, `get_peft_model`). Deep Research is `/chat`; `thread_id` stays in the URL and `GET /chat/{thread_id}` loads the full transcript. Header **Sign in** opens `/signin` (create an account at `/signup`). Sessions are an HttpOnly cookie (`mp_session`).

Local sqlite instead: `--data-dir /tmp/mp-aiml` after `uv run mp ingest tests/fixtures/eval_aiml/research.zip --data-dir /tmp/mp-aiml --process`. Tiny fixture: `--data-dir /tmp/mp-simple` after the simple_mix ingest above.

`POST /auth/signup` `{name, email, password}` and `POST /auth/signin` `{email, password}` set the session cookie. `GET /auth/me` returns `{user_id, name, email}` or 401. `POST /auth/signout` clears it. `POST /search` `{query, page?, page_size?, material_type?}` returns ranked **materials** (hop-1 only, default 10 per page, max 20), `page_count` / `total` for the cached window (cap 100), and a Langfuse `trace_url` when keys are set. Query vectors and that hop-1 window are cached in Redis (`REDIS_URL`, compose Redis on `6379`, prefix `mp:`); paging does not re-embed. Memory cache is used when Redis is down. `POST /chat` `{query, mode?, thread_id?}` runs the Deep Research agent (`quick` | `standard` | `deep`) and returns a cited report plus `thread_id` (hop 1/2 stay 5/20). Pass `thread_id` back to continue the same chat. Signed-in chats store `user_id`; `GET /chats` lists that user's threads only (empty when signed out). `GET /chat/{thread_id}` returns the full transcript from Postgres (`DATABASE_URL`, or sqlite under `--data-dir`) when the thread is yours or was created unsigned. The agent still plans from a compact working set, not this transcript. Checkpoints go to sqlite under `--data-dir` (`langgraph.sqlite`) or Postgres database `langgraph` with `--postgres`. `GET /health` is liveness only. `--postgres` uses `DATABASE_URL`, MinIO, and Qdrant. Match `QDRANT_COLLECTION` and `EMBEDDER` to the ingest (AIML prod is `research_aiml` + `bge-m3`). Chat uses `LLM_BASE_URL` when set. CORS allows the Vite origin (`CORS_ORIGINS`) with credentials.

Citations look like `paper.pdf page 1` or `src/api.py lines 1-2`. `tests/` is not indexed.

`--trace` prints the agent span tree and the Langfuse trace URL when keys are set (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`). Nested node spans and named LLM generations go to Langfuse. Signed-in chats set Langfuse `user_id` (and `session_id` is the thread). Each `retrieve` span contains `hop1` (5 materials), `hop2` (units in those materials), `rerank` (on or off), `boost` (same-source), and `diversity` (units per material). Outputs are locators and scores, not unit bodies.

A larger dump lives at `tests/fixtures/mixed_zip/research.zip`. Ranking traps live at `tests/fixtures/eval_hard/research.zip`. A long treatise for chunk-size sweeps lives at `tests/fixtures/eval_long/research.zip`.

A real AI/ML corpus (Jurafsky & Martin SLP3 draft, arXiv LLM papers, Hugging Face GitHub trees, PyPI wheels, a DJL JAR) is **not in git**. The ingest pipeline still takes a local path only; the fixture builder downloads first:

```bash
uv run mp eval-aiml --build-only
uv run mp eval-aiml --skip-build --data-dir /tmp/mp-aiml --lexical-only
EVAL_AIML=1 uv run pytest tests/unit/eval/test_eval_aiml.py -k ingest
```

The retrieve table is printed to stdout and written to `{data-dir}/eval_aiml_report.txt` (for example `/tmp/mp-aiml/eval_aiml_report.txt`). Re-score an existing sqlite ingest without rebuilding:

```bash
uv run mp eval --data-dir /tmp/mp-aiml \
  --cases tests/fixtures/eval/eval_aiml.json --lexical-only
```

`--lexical-only` is the cheap gate: sqlite, fake embedder, no reranker, deterministic analysis. Production-style scoring uses compose (Postgres, MinIO, Qdrant, Langfuse) plus BGE-M3, the v2-m3 reranker, and LLM analysis. `.env` still supplies URLs, keys, and `LLM_BASE_URL`; `EMBEDDER` / `RERANKER` / `ANALYZER` are ignored. Vectors go to Qdrant collection `research_aiml` so they are not mixed with the fake-embedder run:

```bash
docker compose up -d
uv run mp eval-aiml --skip-build --prod --data-dir /tmp/mp-aiml-prod
```

That run scores lexical and semantic cases, traces the agent on Langfuse, and writes `/tmp/mp-aiml-prod/eval_aiml_report.txt`. Re-score without ingesting again:

```bash
uv run mp eval-aiml --skip-build --prod --skip-ingest \
  --data-dir /tmp/mp-aiml-prod
```

SLP3 hierarchical LLM analysis is slow. Cache and `tests/fixtures/eval_aiml/research.zip` are gitignored. SLP3 is class/print use; do not commit the PDF.

## Dagster pipeline

Two jobs and one sensor:

| Asset | Role |
| --- | --- |
| `ingest_source_job` | Discover materials from a file, directory, or ZIP |
| `process_material_job` | Classify, extract, analyze, index, and build `ResearchMaterial` for one material |
| `pending_materials_sensor` | Claim `DISCOVERED` materials and launch process runs |

Default resource: SQLite at `/tmp/material-platform/material.db`, files under `/tmp/material-platform/store`. Concurrency pool `document_extraction` is limited to 4 (see `dagster.yaml`).

### Start the UI

Dagster loads instance config (`dagster.yaml`) from `$DAGSTER_HOME`, not from the repo root automatically.

```bash
uv sync --group dev
mkdir -p .dagster
cp dagster.yaml .dagster/dagster.yaml
export DAGSTER_HOME="$(pwd)/.dagster"
uv run dagster dev -w workspace.yaml
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000).

### 1. Ingest a source

1. Open **Jobs → ingest_source_job → Launchpad**.
2. Set the path to an absolute file, directory, or ZIP:

```yaml
ops:
  ingest_source:
    config:
      path: /home/cool/Workplaces/Deep-Research/tests/fixtures/mixed_zip/research.zip
```

3. Launch the run.

The op returns the discovered `material_id` list. Materials land in status `DISCOVERED`.

To keep data somewhere other than `/tmp/material-platform`:

```yaml
resources:
  platform:
    config:
      data_dir: /tmp/material-platform
      use_sqlite: true
ops:
  ingest_source:
    config:
      path: /absolute/path/to/source
```

### 2. Process materials

**Sensor (recommended).** `pending_materials_sensor` starts **stopped**. In **Automation / Sensors**, turn it on. Every 15 seconds it claims up to 50 `DISCOVERED` rows (`FOR UPDATE SKIP LOCKED` on Postgres) and launches `process_material_job` with run key `{material_id}:{pipeline_version}`.

**Manual.** Open **Jobs → process_material_job → Launchpad**:

```yaml
ops:
  process_material:
    config:
      material_id: "<uuid from ingest>"
```

Successful process runs mark the material `READY`. Failures mark it `FAILED`; a later run can claim and retry that material alone. Siblings are not re-queued.

### Optional: Postgres, MinIO, Qdrant, and Langfuse

```bash
docker compose up -d
uv run alembic upgrade head
```

Langfuse reuses the same Postgres (`langfuse` database) and MinIO (`langfuse` bucket). UI: [http://localhost:3100](http://localhost:3100) (Dagster stays on 3000). Login `langfuse@example.com` / `langfuselocal`. Copy `.env.example` keys (`pk-lf-local` / `sk-lf-local`) so the agent ships traces.

LangGraph reuses the same Postgres (`langgraph` database) for chat checkpoints and the same Qdrant (`langgraph` collection, hybrid dense+sparse 1024) for a later agent store. `docker compose up` creates both. Local sqlite uses `langgraph.sqlite` under `--data-dir`. Checkpoint tables are created when Runtime first opens the checkpointer.

Production-like path (Postgres, MinIO, Qdrant, BGE-M3, reranker, LLM analysis + agent, Langfuse). Needs compose up, Ollama (or `LLM_BASE_URL`), FlagEmbedding, and `scripts/download_bge.py`:

```bash
docker compose up -d
uv run alembic upgrade head
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install FlagEmbedding
uv run python scripts/download_bge.py
uv run python scripts/e2e_research.py
```

That ingests `tests/fixtures/simple_mix/research.zip` into Qdrant collection `research_e2e` (so BGE vectors are not mixed with the fake embedder), then runs the agent with `--llm --trace`. `.env` still supplies compose URLs, Langfuse keys, and `LLM_BASE_URL`; the script overrides `EMBEDDER` / `RERANKER` / `ANALYZER`. Override `--source` / `--query`. `--skip-ingest` reruns only the agent.

In the Launchpad, point the resource at env-configured Postgres, MinIO, and Qdrant:

```yaml
resources:
  platform:
    config:
      use_sqlite: false
      data_dir: /tmp/material-platform
```

`DATABASE_URL`, MinIO, and `QDRANT_URL` come from `.env` (see `.env.example`). Scratch/workspace stay under `data_dir`; object bytes go to the MinIO bucket; retrieval lives in Qdrant. Default `EMBEDDER=fake` is hashed dense+sparse for tests and local smoke. Set `EMBEDDER=bge-m3` after installing FlagEmbedding for production hybrid search.

CLI against the same stack:

```bash
uv run mp ingest tests/fixtures/mixed_zip/research.zip \
  --postgres --process
uv run mp search "Introduction to materials" --postgres
uv run mp search "handle_request" --postgres \
  --material-type project
uv run mp serve --postgres
```

Gate 14 (no duplicate Materials after a new Dagster resource against this stack):

```bash
LIVE_COMPOSE=1 uv run pytest tests/integration/test_compose_reingest.py
```

## Layout

```
defs/                 Dagster jobs, sensor, PlatformResource
src/material_platform/
  api/                FastAPI search and chat
  application/        Runtime, ingest, process, select
  cli/                mp ingest / search / chat / serve
  discovery/          boundary detectors, ZIP expansion
  analysis/           deterministic MaterialAnalysis
  agent/              Deep Research plan / retrieve / cited report
  eval/               labeled retrieval scoring, AIML, prod knobs
  index/              Qdrant hybrid search (BGE-M3 or fake embedder)
  infrastructure/     stores, embedder, optional hop-2 reranker
  research/           ResearchMaterial builder
scripts/              download_bge.py, e2e_research.py
migrations/           Alembic (identities and state)
tests/fixtures/       mixed ZIP used in tests and the example ingest
```
