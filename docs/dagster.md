# Dagster ops

Dagster is optional. The CLI (`mp ingest --process`) can discover and process without it. Use Dagster when you want a watched inbox of zips, isolated retries, and concurrency pools.

Jobs use the same `Runtime` as `mp serve --postgres` / `mp ingest --postgres`. They read `Settings()` from `.env`.

### What we keep vs what we do not

The inbox (local folder, NFS mount, or FTP/storage share) **owns the source archive**. We read it once for that job. After materials are copied, the zip can disappear. `raw_uri` is only the locator used for that run (`file://…` today).

| Place | Durable? | What |
| --- | --- | --- |
| Inbox / FTP / storage server | Their store, not ours | Source zip or tree. We do not upload or retain it |
| `data_dir` scratch | No | Temporary expand while Discovery runs |
| Postgres | Yes | Source identity (name, sha256, status), materials, process/discovery runs |
| MinIO | Yes | Material content + extract artifacts (classification, analysis, research JSON) |
| Qdrant | Yes | Embedded units after process |

Chat and search stay on FastAPI. They are not Dagster jobs.

First inbox check and remaining inbox work: [Inbox](inbox.md). HTTP switch: [Inference](inference.md). Open list: [Todos](todos.md).

## Mechanism

```text
INGEST_DIRECTORY (local path or mounted FTP/storage share)
        │
        ▼
ingest_directory_sensor          every 15s, starts STOPPED
        │  one RunRequest per new/changed zip
        ▼
ingest_source_job                one Dagster run = one archive
        │  expand zip locally; materials + discovery manifest → MinIO
        │  Source + DISCOVERED rows → Postgres
        ▼
pending_materials_sensor         every 15s, starts STOPPED
        │  claims up to 50 DISCOVERED / FAILED
        ▼
process_material_job             one Dagster run = one material
        │  classify → extract → analyze → embed → Qdrant
        ▼
READY in Postgres; extract artifacts in MinIO; units in Qdrant
```

A zip is a **Source**, never a Material. Discovery expands that zip and splits it into materials. Process then runs per material.

One bad zip fails only its `ingest_source_job`. Sibling zips keep going. One bad material fails only its `process_material_job`.

Do not point `ingest_source_job` at the inbox folder if you want that isolation. A directory path there is one Source: Discovery walks everything, and one unsafe archive fails the whole run.

## Jobs

| Job | Config | What it does |
| --- | --- | --- |
| `ingest_source_job` | `path` (absolute file) | Discover one source. Copy materials to MinIO. Prefer one zip. |
| `process_material_job` | `material_id` | Classify, extract, analyze, embed, mark READY or FAILED |

### `ingest_source_job`

Launchpad:

```yaml
ops:
  ingest_source:
    config:
      path: /data/inbox/paper-pack.zip
resources:
  platform:
    config:
      use_sqlite: false
      data_dir: /tmp/material-platform
      ingest_dir: /data/inbox
```

`use_sqlite: false` (the Definitions default) loads `.env`: `DATABASE_URL`, `MINIO_*`, `QDRANT_URL`, `QDRANT_COLLECTION`, `EMBEDDER`, `LLM_BASE_URL`. Match `mp serve --postgres`. `data_dir` is scratch for zip expand. The archive is not uploaded.

`path` must be readable on the Dagster worker (local disk or a mounted share). Nested zips inside the archive stay inside Discovery (`MAX_ARCHIVE_DEPTH`). They do not get their own ingest job.

### `process_material_job`

Usually launched by `pending_materials_sensor`. Manual retry of one material:

```yaml
ops:
  process_material:
    config:
      material_id: 11111111-1111-1111-1111-111111111111
```

Pool: `document_extraction`. Retry: 2 attempts, 2s delay.

## Sensors

Both start **STOPPED**. Turn them on in the Dagster UI after the inbox path and storage match the corpus you want.

| Sensor | Interval | Emits |
| --- | --- | --- |
| `ingest_directory_sensor` | 15s | `ingest_source_job` per new or changed top-level archive |
| `pending_materials_sensor` | 15s | `process_material_job` per claimed material |

### Point the ingest directory

`INGEST_DIRECTORY` is wherever the worker can **see** source archives. That can be:

| Inbox | Example |
| --- | --- |
| Local folder | `$(pwd)/inbox` (writable; do not use `/data` unless you own it) |
| Mount of an FTP / NAS / storage server | `/mnt/research-drop` |

We do not manage that store. List **finished** top-level expand archives (`.zip`, `.tar`, `.tar.*`, `.tgz`, `.7z`). Loose PDFs, project dirs, nested zips, hidden names, and junk (`.DS_Store`) are skipped.

Set one of:

| Knob | Where |
| --- | --- |
| `INGEST_DIRECTORY` | Env when you start `dagster dev` |
| `platform.ingest_dir` | Resource config (Launchpad / Definitions) |

Empty path → sensor skips (`No ingest directory`).

Cursor is `{absolute_path: mtime_ns:size}`. A rewrite gets a new fingerprint and a new job. If the remote store removes a file, it leaves the cursor; if the same path appears again, it is ingested once more.

Run key: `ingest:{filename}:{hash}` so Dagster will not enqueue a duplicate for the same fingerprint.

### Process queue

`pending_materials_sensor` claims up to 50 `DISCOVERED` or `FAILED` rows (`PIPELINE_VERSION` run key `{material_id}:{pipeline_version}`). Claim moves the row to `PROCESSING` so two ticks do not double-launch.

## Resource: `platform`

| Field | Default | Meaning |
| --- | --- | --- |
| `use_sqlite` | `false` | `false`: `.env` → Postgres + MinIO + Qdrant. `true`: local sqlite + filesystem (tests / no Docker) |
| `data_dir` | `/tmp/material-platform` | Expand scratch. With sqlite, also the db / local store / embedded Qdrant |
| `ingest_dir` | `""` (or `$INGEST_DIRECTORY`) | Folder the directory sensor watches |

| `use_sqlite` | Identities | Material + extract bytes | Vectors |
| --- | --- | --- | --- |
| `false` | `DATABASE_URL` (Postgres) | MinIO (`MINIO_*`) | `QDRANT_URL` + `QDRANT_COLLECTION` |
| `true` | sqlite `data_dir/material.db` | files under `data_dir/store` | embedded Qdrant in `data_dir` |

Need compose up and `alembic upgrade head` before turning sensors on. Same collection and embedder as search / `mp serve`.

## Embed / rerank / LLM

Dagster does not host models. Process and search call whatever backend `Settings` selects:

| Knob | Local (test now) | HTTP (later) |
| --- | --- | --- |
| `EMBEDDER` | `bge-m3` (FlagEmbedding in-process) | `http` + `EMBED_BASE_URL` (OpenAI `/embeddings`) |
| `RERANKER` | `bge-v2-m3` (FlagEmbedding in-process) | `http` + `RERANK_BASE_URL` (`/rerank`) |
| `ANALYZER` / chat | — | `LLM_BASE_URL` (already HTTP) |

Same `Embedder` / `Reranker` protocols either way. HTTP embed is dense-only (sparse placeholder); keep `DENSE_SIZE` (1024) matched to the Qdrant collection.

## Concurrency

`dagster.yaml` (copy into `$DAGSTER_HOME`):

```yaml
concurrency:
  pools:
    default_limit: 4
    granularity: op
```

Named keys like `document_extraction: 4` are **not** valid in this Dagster version. `pools` only accepts `default_limit`, `granularity`, and `op_granularity_run_buffer`.

| What | Effect |
| --- | --- |
| `default_limit` | Max concurrent ops, including ingest and `process_material` (`pool=document_extraction`) |
| UI → Deployment → Concurrency | Optional extra cap on the `document_extraction` pool |

When embed/rerank are HTTP, scale them on that box. Local BGE still runs in the worker — keep `default_limit` modest until then.

## Image

**Kubernetes:** shared official `docker.io/dagster/dagster-celery-k8s` (webserver + daemon). This repo is one code location / run image (`material-platform`, `dagster-k8s` extra). Do not put other projects into that image.

**Compose:** local shortcut — `dagster-web` / `dagster-daemon` use `material-platform` on one box.

Air-gap Helm: [Air-gap](airgap.md) → `scripts/install-dagster.sh` (`dagster-system` + `material-research`).

## Compose (UI + daemon)

```bash
mkdir -p inbox
docker compose up -d --build
uv run alembic upgrade head
```

| Service | Image | Role |
| --- | --- | --- |
| `dagster-web` | `material-platform:0.1.0` | UI at [http://127.0.0.1:3000](http://127.0.0.1:3000) |
| `dagster-daemon` | `material-platform:0.1.0` | Sensors and run launcher |

Inbox: host `./inbox` → container `/inbox` (`INGEST_DIRECTORY`). Instance config: `./dagster.yaml` → `/opt/dagster/dagster.yaml`. Run history: volume `dagster-home`.

Inside the container, hostnames are `postgres`, `minio`, `qdrant` (not `localhost`). `.env` `LLM_BASE_URL` is passed through (LAN vLLM is fine). The image has no FlagEmbedding — process jobs need `EMBEDDER=http` / `RERANKER=http`.

Do not run `dagster dev` on 3000 at the same time as compose.

## Host `dagster dev` (debug)

```bash
mkdir -p .dagster inbox
cp dagster.yaml .dagster/dagster.yaml
export DAGSTER_HOME="$(pwd)/.dagster"
export INGEST_DIRECTORY="$(pwd)/inbox"
uv run dagster dev -w workspace.yaml
```

Dagster may warn that the repo-root `dagster.yaml` is unused. That is expected: the instance reads `$DAGSTER_HOME/dagster.yaml` only.

1. Confirm `platform.use_sqlite` is `false` (Definitions default).
2. Turn on `ingest_directory_sensor`.
3. Turn on `pending_materials_sensor`.
4. Put finished zips where `$INGEST_DIRECTORY` can read them (local or mounted share).

To ingest one zip without the watcher, launch `ingest_source_job` with that file's absolute path, then leave the process sensor on.

Reset the directory sensor cursor in the UI if you need to re-queue every zip currently in the folder.

## What is not in Dagster

| Work | Where it runs |
| --- | --- |
| Source archives | External inbox (local / FTP / storage). Not MinIO |
| Embed / rerank / LLM | `EMBEDDER` / `RERANKER` / `LLM_BASE_URL` (local BGE or HTTP) |
| Search hop-1 | FastAPI `POST /search` |
| Deep Research chat | FastAPI `POST /chat` + LangGraph |
| Auth / threads | FastAPI |
| CLI ingest + `--process` | `mp` in-process (same services, no jobs) |
