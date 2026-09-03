# Project structure

```text
defs/                     Dagster jobs, sensors, PlatformResource
docker/                   Container entrypoint
Dockerfile                Dagster web + daemon image
docs/                     Architecture, setup, env, pipeline, agent, Dagster, …
migrations/               Alembic (identities and state)
scripts/                  download_bge.py, e2e_research.py
src/material_platform/
  agent/                  LangGraph Deep Research nodes
  analysis/               Deterministic / LLM MaterialAnalysis
  api/                    FastAPI app, routes, schemas
  application/            Use-case services + Runtime
  classification/         Material type rules
  cli/                    mp ingest / search / chat / serve
  config.py               Settings from env / .env
  discovery/              Boundaries, safe archive expand
  domain/                 Contracts, ports, budgets
  eval/                   Labeled retrieval + AIML
  extraction/             Format extractors + chunking
  infrastructure/         DB, MinIO, Qdrant, LLM, tracing
  research/               ResearchMaterial builder
web/                      Vite + React UI
tests/fixtures/           ZIP corpora for ingest / eval
```

## Domain

| File | What |
| --- | --- |
| `base.py` | Frozen `Contract` |
| `enums.py` | Status and type enums |
| `source.py`, `material.py`, `artifact.py` | Ingest identities |
| `research_material.py` | `ContentUnit`, `MaterialFile`, `ResearchMaterial` |
| `research.py` | Agent contracts (`ResearchPlan`, `ResearchReport`, `ChatTurn`) |
| `budgets.py` | `quick` / `standard` / `deep` |
| `profile.py` | `MaterialProfile`, analysis budgets |
| `classification.py` | `ClassificationDecision`, persisted classification |
| `protocols.py` | `Analyzer`, `LlmClient` |
| `citation.py`, `index_entry.py` | Retrieval hits |

## Application services

| Service | File | Job |
| --- | --- | --- |
| `Runtime` | `runtime.py` | Engine, sessions, store, index, analyzer |
| `IngestSourceService` | `ingest_source.py` | Path → Source + DISCOVERED materials |
| `ProcessMaterialService` | `process_material.py` | Classify → extract → analyze → index |
| `IndexService` | `index.py` | Embed, Qdrant replace/search, hop-1 cache |
| `DeepResearchService` | `deep_research.py` | Hop-1/2 `select` used by the agent |
| `AuthService` | `auth.py` | Sign up / in / out, session cookie |
| `ChatHistoryService` | `chat_history.py` | Threads scoped by `user_id` |
| `WorkQueue` | `queue.py` | Claim DISCOVERED / FAILED for Dagster |

## Agent

| File | Node / role |
| --- | --- |
| `graph.py` | `StateGraph`, `run_agent` |
| `service.py` | `ResearchAgent` facade |
| `state.py` | Mutable graph state |
| `planner.py` | `plan` |
| `retrieve.py` | `retrieve` → `DeepResearch.select` |
| `extract.py` | Evidence from units |
| `coverage.py` | Covered / gap / follow-up |
| `findings.py` | Claims + stances |
| `synthesizer.py` | Cited report |
| `validate.py` | Drop `__material__` / empty locators |
| `compact.py` | Conversation fold for continue |

## Infrastructure

| Package | Adapter |
| --- | --- |
| `database/` | SQLAlchemy engine, rows, repos, auth, chat history |
| `object_store/` | Filesystem or MinIO |
| `qdrant/` | Client, store, point payload (`INDEX_VERSION=v2`) |
| `embedding/` | `Embedder` protocol: fake, local BGE-M3, HTTP `/embeddings` |
| `llm/` | OpenAI-compatible HTTP client |
| `tracing/` | Tracer protocol, Langfuse, `TracedLlmClient` |
| `rerank/` | `Reranker` protocol: local BGE, HTTP `/rerank` |
| `cache.py` | Redis or memory query cache |

## Web

`web/src/pages` — search, `/chat`, `/signin`, `/signup`. Vite proxies `/search`, `/auth`, `/chat`, `/chats`, `/health` to `mp serve` on port 8000.
