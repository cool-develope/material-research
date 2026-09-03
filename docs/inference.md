# Embed, rerank, LLM

Callers use `Embedder.embed` and `Reranker.score`. The factory picks the backend. Dagster does not host models. Env: [Environment](environment.md).

| Knob | Local (now) | HTTP (later) |
| --- | --- | --- |
| `EMBEDDER` | `bge-m3` — FlagEmbedding in-process | `http` + `EMBED_BASE_URL` |
| `RERANKER` | `bge-v2-m3` — FlagEmbedding in-process | `http` + `RERANK_BASE_URL` |
| `ANALYZER` / chat | — | `LLM_BASE_URL` (already HTTP) |

`fake` / `off` stay for pytest. Collection dimension is `DENSE_SIZE` = 1024. Ingest and search must use the same `EMBEDDER`.

## Switch to HTTP

When the inference box is up:

```bash
EMBEDDER=http
EMBED_BASE_URL=http://embed:8000/v1
EMBED_API_KEY=embed
EMBED_MODEL=BAAI/bge-m3

RERANKER=http
RERANK_BASE_URL=http://rerank:8080
RERANK_API_KEY=rerank
RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

Keep `LLM_BASE_URL` as today. Do not mix `bge-m3` vectors and `http` vectors in one `QDRANT_COLLECTION`.

Hit the server once from the same machine that runs process / `mp serve`. If the status or JSON shape is wrong, change `infrastructure/embedding/http.py` or `infrastructure/rerank/http.py` — not the jobs.

## Embed contract (`EMBEDDER=http`)

`POST {EMBED_BASE_URL}/embeddings`

```json
{ "model": "BAAI/bge-m3", "input": "text" }
```

```json
{ "data": [{ "embedding": [0.0, 0.1], "index": 0 }] }
```

Authorization: `Bearer {EMBED_API_KEY}`. Dense length must be 1024.

**Gap:** response sparse weights are ignored. We store `sparse_indices=(0,)`, `sparse_values=(1.0,)`. Hop-1 dense still works. Lexical / hybrid is weaker until the API returns sparse (or we stop writing sparse).

## Rerank contract (`RERANKER=http`)

`POST {RERANK_BASE_URL}/rerank`

```json
{ "model": "BAAI/bge-reranker-v2-m3", "query": "q", "texts": ["a", "b"] }
```

Accepted responses (same length as `texts`):

```json
{ "scores": [0.2, 0.9] }
```

```json
{ "results": [{ "index": 1, "relevance_score": 0.1 }, { "index": 0, "relevance_score": 0.8 }] }
```

`score` is an alias for `relevance_score`. Texts are clipped to 2048 chars before the call.

**Gap:** unit tests mock `urlopen`. TEI / vLLM / Cohere may use another path or field names. Adjust the client when the real server is chosen. Rerank is hop-2 in the agent, not a Dagster pool.

## LLM

Already `POST {LLM_BASE_URL}/chat/completions` with `response_format: json_object`. No factory change for HTTP.
