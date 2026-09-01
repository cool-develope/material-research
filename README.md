# Material Platform

Discover independent research materials from files, directories, and ZIP archives, then process each one into a `ResearchMaterial` for Deep Research.

Python 3.12, managed with uv. PostgreSQL owns identities and state; the object store owns bytes; the Discovery Engine owns Material boundaries; Dagster owns execution.

## Setup

```bash
uv sync --group dev
uv run pytest
```

Copy `.env.example` to `.env` when you start using Postgres and MinIO.

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
EMBEDDER=bge-m3 uv run python scripts/ingest_local.py \
  tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-bge --process
EMBEDDER=bge-m3 uv run python scripts/research_query.py "handle_request" \
  --data-dir /tmp/mp-bge
```

## Local ingest (no Dagster)

SQLite + filesystem store, no Docker:

```bash
uv run python scripts/ingest_local.py tests/fixtures/simple_mix/research.zip \
  --data-dir /tmp/mp-simple --process
uv run python scripts/research_query.py "Introduction to materials" \
  --data-dir /tmp/mp-simple
uv run python scripts/research_query.py "handle_request" \
  --data-dir /tmp/mp-simple
```

That zip is three Materials (`paper.pdf`, `backend/`, `dataset/`). Use a **fresh `--data-dir`** per ingest so older sources are not mixed into sibling lists.

Citations look like `paper.pdf page 1` or `src/api.py lines 1-2`. `tests/` is not indexed.

A larger dump lives at `tests/fixtures/mixed_zip/research.zip`.

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

### Optional: Postgres, MinIO, and Qdrant

```bash
docker compose up -d
uv run alembic upgrade head
```

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
uv run python scripts/ingest_local.py tests/fixtures/mixed_zip/research.zip \
  --postgres --process
uv run python scripts/research_query.py "Introduction to materials" --postgres
```

## Layout

```
defs/                 Dagster jobs, sensor, PlatformResource
src/material_platform/
  discovery/          boundary detectors, ZIP expansion
  application/        ingest, process, claim queue, Deep Research select
  analysis/           deterministic MaterialAnalysis
  index/              Qdrant hybrid search (BGE-M3 or fake embedder)
  research/           ResearchMaterial builder
migrations/           Alembic (identities and state)
tests/fixtures/       mixed ZIP used in tests and the example ingest
```
