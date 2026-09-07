# Remaining work

Open items after the Dagster / storage / inference cut. Jobs and sensors: [Dagster](dagster.md). HTTP shapes: [Inference](inference.md). Inbox rules: [Inbox](inbox.md).

| # | Status | Item | Issue | Doc |
| --- | --- | --- | --- | --- |
| 1 | Done | First inbox run: sensors on, one finished zip, MinIO has materials only | — | [Inbox](inbox.md#first-run) |
| 2 | Done | Switch `EMBEDDER` / `RERANKER` to `http` and match the live API | — | [Inference](inference.md#switch-to-http) |
| 3 | If the drop is a network share | Ignore zips still being copied (settle window) | [#1](https://github.com/cool-develope/material-research/issues/1) | [Inbox](inbox.md#copy-in-progress) |
| 4 | Later | Fetch from FTP / object store if you will not mount the share | [#2](https://github.com/cool-develope/material-research/issues/2) | [Inbox](inbox.md#remote-fetch) |

Not bugs in the current cut. Do not undo per-zip jobs, Postgres/MinIO, or “zip stays on the inbox.”

## Also know

| Fact | Why it matters |
| --- | --- |
| Local BGE still loads in the Dagster worker | `default_limit: 4` caps ingest and extract together. Tighten in the UI if BGE RAM is tight. |
| HTTP embed is dense-only | Sparse slot is a placeholder. Hybrid lexical retrieval is weaker on `EMBEDDER=http` until the API returns sparse. [#3](https://github.com/cool-develope/material-research/issues/3) |
| `INGEST_DIRECTORY` is not a `Settings` field | Only Dagster reads it. `mp ingest` still wants an explicit path. |
| `$DAGSTER_HOME/dagster.yaml` is a copy | Recopy after template changes. `pools` may only have `default_limit` / `granularity`. |
