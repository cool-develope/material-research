# Architecture

The Python package is a hexagonal / clean split. Domain and application do not talk to Docker, FastAPI, or vendor SDKs. Adapters live in `infrastructure/`. HTTP and CLI are thin entry points.

```
web (Vite) ──proxy──► api (FastAPI) ──► application services
cli (mp) ───────────► application services
defs (Dagster) ─────► application services

application ──► domain models / ports
application ──► infrastructure adapters
agent ────────► domain ports (LlmClient) + application IndexService
```

## Layers

| Layer | Role | May depend on |
| --- | --- | --- |
| `domain/` | Frozen contracts, budgets, ports (`Analyzer`, `LlmClient`) | Nothing outside domain |
| `application/` | Use cases: ingest, process, index, auth, chat history, runtime | domain + infrastructure |
| `infrastructure/` | Postgres, MinIO, Qdrant, Redis, embeddings, LLM HTTP, Langfuse | vendor SDKs, domain types |
| `discovery/`, `classification/`, `extraction/`, `analysis/` | Bounded pipelines that turn bytes into units and `MaterialAnalysis` | domain + each other |
| `agent/` | LangGraph Deep Research loop | domain + application index + tracing |
| `api/`, `cli/`, `defs/` | HTTP, CLI, Dagster | application |

## Ownership

| Concern | Owner |
| --- | --- |
| Identities, materials, sessions, chat threads | Postgres (`DATABASE_URL`) or sqlite under `--data-dir` |
| Material content + extract artifacts | MinIO or filesystem object store |
| Source archives | External inbox (local folder or FTP/storage mount). Not retained |
| Material boundaries | Discovery engine |
| Retrieval vectors | Qdrant (`QDRANT_COLLECTION`) |
| Query cache | Redis (`REDIS_URL`), memory fallback |
| Agent checkpoints | sqlite `langgraph.sqlite` or Postgres `langgraph` |
| Traces | Langfuse when keys are set |
| Execution scheduling | Dagster (optional; CLI can ingest/process without it) |

## Request paths

**Search (anonymous).** `POST /search` → `IndexService.search_materials` → embed query → hop-1 material window (cached) → page slice.

**Chat (signed in).** `POST /chat` → `AuthService` cookie → `DeepResearchService.select` → `ResearchAgent` (plan / retrieve / extract / write) → `ChatHistoryService.record_turn` with `user_id`.

**Ingest.** Path or ZIP → `IngestSourceService` → discovery → `Material` rows in `DISCOVERED`.

**Process.** `ProcessMaterialService` → classify → extract → analyze → `build_research_material` → `IndexService.replace`.
