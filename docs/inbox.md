# Inbox

The inbox is whoever owns the source archives: a local folder, or a mount of an FTP / NAS / storage server. We read a file for one ingest run. We do not upload or retain the zip. Ops: [Dagster](dagster.md).

`INGEST_DIRECTORY` (or `platform.ingest_dir`) is that path. It is **not** a `Settings` field. `mp ingest PATH` still takes an explicit path.

## What we keep

| After a successful ingest | Kept? |
| --- | --- |
| Source zip / tree on the inbox | No (their store) |
| Expand scratch under `data_dir` | No |
| Source row (name, sha256, `raw_uri`, status) | Yes — Postgres |
| Material bytes + discovery / extract JSON | Yes — MinIO |
| Process / discovery run rows | Yes — Postgres |
| Vectors | Yes — Qdrant after process |

`raw_uri` is `file://…` for this run only. If the inbox deletes the zip later, that is expected.

The sensor lists **finished** top-level expand archives (`.zip`, `.tar*`, `.tgz`, `.7z`). Loose PDFs, nested zips, hidden names, and junk are skipped.

## First run

```bash
mkdir -p inbox
docker compose up -d --build
uv run alembic upgrade head
```

UI: [http://127.0.0.1:3000](http://127.0.0.1:3000). Inbox is `./inbox` on the host (`/inbox` in the container). Use a path you can write; `/data/inbox` needs root.

1. Confirm `platform.use_sqlite` is `false`.
2. Turn on `ingest_directory_sensor` and `pending_materials_sensor`.
3. Copy **one finished** zip into `inbox/` (do not copy while it is still growing).
4. Expect one `ingest_source_job`, then one `process_material_job` per discovered material.

Check MinIO bucket `material`:

- Present: `materials/{id}/content/…`, `materials/{id}/content-manifest.json`, `manifests/…`, later `artifacts/…`
- Absent: `raw/{source_id}/original`

Postgres should have a Source (sha256, `file://…`) and DISCOVERED → READY materials. Search with the same `EMBEDDER` and `QDRANT_COLLECTION` as process.

If `$DAGSTER_HOME/dagster.yaml` still has `document_extraction`, `embedding`, or `llm` under `pools`, recopy from the repo `dagster.yaml`. This Dagster version only allows `default_limit` / `granularity` there.

## Copy-in-progress

The sensor fingerprints `mtime_ns:size`. A zip that is still being written can be ingested too early (unsafe or truncated archive).

**Todo:** skip files newer than a few seconds (settle), then pick them up on the next 15s tick. Need this if the inbox is a network drop, not a local `mv` of a complete file.

Until that exists: write to a sibling temp name, then rename onto `INGEST_DIRECTORY`.

## Remote fetch

Today the worker must **see** the file on a POSIX path (`file://`). Mount the FTP/storage share, or sync it there.

**Todo (later):** a fetcher that pulls `ftp://` / object-store URIs into scratch, then runs the same `ingest_source_job`. Do not store that download in MinIO. Only add this if you will not mount the share.
