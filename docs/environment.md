# Environment

Settings live in `src/material_platform/config.py`. Local runs load `.env`. Copy `.env.example` for a production-ready compose profile (`EMBEDDER=bge-m3`, `RERANKER=bge-v2-m3`, `ANALYZER=llm`). **Pytest does not** read `.env` — it pins `EMBEDDER=fake`, `RERANKER=off`, `ANALYZER=deterministic`.

`scripts/e2e_research.py` and `mp eval-aiml --prod` force BGE + reranker + LLM on top of `.env` URLs and keys.

## Two stacks

| Mode | Flag | Database | Material + extract bytes | Vectors |
| --- | --- | --- | --- | --- |
| Local | `--data-dir DIR` | sqlite `DIR/material.db` | files under `DIR` | embedded Qdrant in `DIR` |
| Compose | `--postgres` | `DATABASE_URL` | MinIO (not the inbox zip) | `QDRANT_URL` + `QDRANT_COLLECTION` |

`--data-dir` and `--postgres` must not be mixed for one corpus. A BGE ingest into `research_aiml` will not search correctly with `EMBEDDER=fake`.

## Identity and storage

| Variable | Used by | Notes |
| --- | --- | --- |
| `DATABASE_URL` | API, CLI `--postgres`, Alembic | Postgres identities, sessions, chat threads |
| `MINIO_*` | Object store | Bucket `material` (compose also has `langfuse`) |
| `WORKSPACE_ROOT` | Scratch / default data dir | Archive expand only |
| `QDRANT_URL` | Index | Compose `http://localhost:6333` |
| `QDRANT_COLLECTION` | Index | Default `research`. AIML prod is `research_aiml`. E2E is `research_e2e` |
| `REDIS_URL` | Search hop-1 cache | Same Redis as Langfuse. Memory fallback if down |
| `COOKIE_SECURE` | Auth cookie | `true` behind HTTPS |

## LangGraph

| Variable | Used by |
| --- | --- |
| `LANGGRAPH_DATABASE_URL` | Checkpoints in Postgres db `langgraph` when `--postgres` |
| `LANGGRAPH_QDRANT_COLLECTION` | Reserved agent store (`langgraph` collection) |

Local sqlite uses `langgraph.sqlite` under `--data-dir`. Tables are created when Runtime first opens the checkpointer.

## Retrieval knobs

| Variable | Values | Effect |
| --- | --- | --- |
| `EMBEDDER` | `fake` \| `bge-m3` \| `http` | Vectors. `bge-m3` is local FlagEmbedding. `http` needs `EMBED_BASE_URL` |
| `EMBED_BASE_URL` | OpenAI-compatible `/v1` | Used when `EMBEDDER=http`. POST `/embeddings` |
| `EMBED_MODEL`, `EMBED_API_KEY` | — | HTTP embed model. Default model is `BGE_MODEL` |
| `EMBED_TIMEOUT_SECONDS` | seconds | Default 120 |
| `BGE_MODEL` | Hugging Face id | Local BGE id, or default HTTP model. Default `BAAI/bge-m3` |
| `RERANKER` | `off` \| `bge-v2-m3` \| `http` | Hop-2 only. `http` needs `RERANK_BASE_URL` |
| `RERANK_BASE_URL` | HTTP origin | POST `/rerank` with `{query, texts}` |
| `RERANK_MODEL`, `RERANK_API_KEY` | — | HTTP rerank model. Default model is `BGE_RERANKER` |
| `RERANK_TIMEOUT_SECONDS` | seconds | Default 120 |
| `BGE_RERANKER` | Hugging Face id | Local rerank id, or default HTTP model |

Pytest stays fake + reranker off. `bge-m3` / `bge-v2-m3` are the current local test hosts. Switch to `http` later without changing callers. LLM analysis is already HTTP (`LLM_BASE_URL`).

## Analysis and agent

| Variable | Values | Effect |
| --- | --- | --- |
| `ANALYZER` | `deterministic` \| `llm` | Process-time `MaterialAnalysis` |
| `LLM_BASE_URL` | OpenAI-compatible URL | Analysis + `mp chat --llm` + `POST /chat` |
| `LLM_API_KEY`, `LLM_MODEL` | — | Passed to `OpenAICompatClient` |
| `LLM_TIMEOUT_SECONDS` | seconds | Default 120 |
| `ANALYSIS_*` | token / file caps | Profile grouping, not retrieval chunk size |
| `AGENT_MODE` | `quick` \| `standard` \| `deep` | Select/plan budgets. Hop 1/2 stay 5/20 |

Retrieval chunks stay 512/64 (`CHUNK_TOKENS` / overlap on Settings; not the analysis knobs).

## Tracing and UI

| Variable | Used by |
| --- | --- |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Agent + search traces. Empty = off |
| `LANGFUSE_HOST` | Compose `http://localhost:3100` |
| `CORS_ORIGINS` | FastAPI CORS for Vite (`5173`) |

Signed-in chats set Langfuse `user_id`. `session_id` is the chat thread.

## Discovery / pipeline versions

| Variable | Meaning |
| --- | --- |
| `DISCOVERY_VERSION` | Boundary detector version stored on the source |
| `PIPELINE_VERSION` | Process run key `{material_id}:{pipeline_version}` |
| `MAX_ARCHIVE_*` | Safe expand caps (files, bytes, depth, ratio, timeout) |

## Dagster

Jobs load the same `Settings()` as `mp --postgres` (`DATABASE_URL`, `MINIO_*`, `QDRANT_*`, `EMBEDDER`). Extra knobs:

| Variable | Meaning |
| --- | --- |
| `INGEST_DIRECTORY` | Folder `ingest_directory_sensor` watches. Compose sets `/inbox` (host `./inbox`). |
| `DAGSTER_HOME` | Instance dir. Compose uses `/opt/dagster`. Host debug uses `.dagster`. |

See [Dagster](dagster.md), [Inbox](inbox.md), [Inference](inference.md). `use_sqlite: true` is tests / no-Docker only.

## Compose ports

| Port | Service |
| --- | --- |
| 5432 | Postgres (`material`, plus `langfuse` and `langgraph` dbs) |
| 6333 | Qdrant |
| 6379 | Redis |
| 8000 | `mp serve` |
| 9000 / 9001 | MinIO / console |
| 3100 | Langfuse UI |
| 3000 | Dagster UI |
| 5173 | Vite |

ClickHouse is Langfuse-only and is not published (would collide with MinIO on 9000).
