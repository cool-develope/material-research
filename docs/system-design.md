# System design

## Names

| Word | Meaning |
| --- | --- |
| **Source** | The local path ingested. One ingest, one Source. A zip is a Source, never a Material. |
| **Material** | One Discovery boundary: paper, project tree, dataset, wheel. |
| **Content unit** | Citable extract (page, line range, symbol). This is what we embed. |
| **Material analysis** | One summary + topics for the whole Material. Not a citation. |
| **Packaged artifact** | Wheel / JAR / npm `.tgz`. One FILE Material. Peek; do not explode. |

Siblings share `source_id`. No knowledge graph.

## Ingest

A source is a file, directory, or ZIP. Discovery walks the tree, expands archives safely, and splits the payload into independent materials (PDF, project root, dataset, artifact).

Each material is stored as:

- identity + status in the database
- material bytes + later extract artifacts in the object store
- status `DISCOVERED` until process runs

The source archive stays on the inbox (local path or mounted FTP/storage). `raw_uri` records that locator for the run. We do not upload or retain the zip.

CLI: `mp ingest PATH [--process] [--data-dir DIR | --postgres]`.

Dagster: point `INGEST_DIRECTORY` at a folder of zips. `ingest_directory_sensor` launches one `ingest_source_job` per zip. `pending_materials_sensor` claims `DISCOVERED` rows and launches `process_material_job` per material. See [Dagster](dagster.md).

## Process

For one material:

1. Classify (`ClassificationDecision`)
2. Extract content units (chunk 512 / overlap 64 by default)
3. Profile + analyze (`deterministic` or `llm`)
4. Build `ResearchMaterial`
5. Embed units + one material-level point
6. Upsert into Qdrant; mark material `READY`

Failures mark the material `FAILED`. A later run can retry that id alone. Detail: [Pipeline](pipeline.md).

## Discovery rules

Local path only. Specific suffix before ZIP magic. Never treat `.whl` / `.jar` / `.docx` as a source ZIP.

| Action | When |
| --- | --- |
| `expand` | `.zip`, `.tar*`, `.7z`, non-npm `.tgz` — container, never a Material |
| `artifact` | `.whl` / `.jar` / npm `.tgz` — one FILE Material |
| `file` | Office, installers, pdf/text/csv, everything else |

Safe expand: no `extractall()`, reject traversal / symlink / encrypted, caps on files / bytes / depth. Ignore `.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, `build`, `__MACOSX`.

Boundary order: ignore → project (this directory’s manifest) → dataset (`data/` with CSVs) → recurse. Stop after a directory becomes a Material.

Project extract: rank identity → entry → API, skip tests/lockfiles, cap 20 files. Documents keep all pages, then window 512/64. Python / Go / JS top-level symbols become `code.symbol`.

## Search

Hop-1 only for the UI and `POST /search`:

1. Embed the query (BGE-M3 or hashed `fake`)
2. Retrieve a material window (cap 100), cache it in Redis
3. Page 10 by default, max 20

Hop-2 (units inside those materials), rerank, same-source boost, and diversity run only inside the Deep Research agent retrieve node. Hop sizes stay 5 / 20 regardless of `quick` / `standard` / `deep`.

```text
query → hop 1  level=material top 5
      → hop 2  level=content_unit AND material_id IN … top 20
      → drop __material__ → Citation
```

Citations look like `paper.pdf page 1` or `src/api.py lines 1-2`. Never cite `__material__`. `tests/` is not indexed.

## Deep Research chat

The graph: plan → retrieve → extract → findings → coverage / gap → write → validate. Detail: [Agent](agent.md).

Budgets (`AGENT_MODE` or request `mode`):

| Mode | Plan questions | Select calls |
| --- | --- | --- |
| `quick` | 2 | 3 |
| `standard` | 6 | 8 |
| `deep` | 8 | 16 |

Anonymous users can search. Research (`POST /chat`, `GET /chat/{thread_id}`) requires a session cookie. Threads are scoped to `user_id`. Langfuse gets `user_id` and `session_id` (thread id) when keys are set.

The API stores the full transcript. The agent plans from a compact working set, not that transcript.

## Auth

Email / password. Sessions are HttpOnly cookies (`mp_session`, SameSite=lax). `COOKIE_SECURE` is for HTTPS.

| Route | Who |
| --- | --- |
| `POST /auth/signup`, `POST /auth/signin` | public |
| `GET /auth/me`, `POST /auth/signout` | cookie |
| `POST /search` | public (optional user on the trace) |
| `POST /chat`, `GET /chat/{id}`, `GET /chats` | signed in |
