# Pipeline

How a source becomes indexed units. Scheduling: [Dagster](dagster.md). What we store: [Inbox](inbox.md). Vectors: [Inference](inference.md).

```text
inbox zip
  → Discovery          materials (PDF, project, dataset, artifact)
  → Process            classify → extract → analyze → ResearchMaterial
  → Index              embed each unit + one material card → Qdrant
```

A zip is a **Source**, never a Material. Each material is processed alone. Failures mark that material `FAILED`.

## What we keep after process

| Object | Where | What it is |
| --- | --- | --- |
| Content unit | MinIO extract JSON + Qdrant | Citable text (page, lines, symbol). This is what we embed |
| Material card | Qdrant `__material__` | Title + summary + topics. Not a citation |
| Material analysis | MinIO `analysis` | One summary / topics / keywords for the whole material |
| Classification | Postgres | Type + subtype + evidence |
| ResearchMaterial | MinIO `research` | Units + analysis + provenance, ready to index |

The inbox zip is not stored. `tests/` is not indexed.

## Discovery (boundaries)

Walk the path. Expand archives safely (no `extractall()`, reject traversal / symlink / encrypted). Ignore `.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, `build`, `__MACOSX`.

| Action | When | Result |
| --- | --- | --- |
| `expand` | `.zip`, `.tar*`, `.7z`, non-npm `.tgz` | Container, not a material |
| `artifact` | `.whl` / `.jar` / npm `.tgz` | One FILE material (peek, do not explode) |
| `file` | PDF, office, text, csv, installers | One FILE material |

Directory order: ignore → project (this dir’s manifest) → dataset (`data/` with CSVs) → recurse. Stop when a directory becomes a material.

## Classify

`classify_files` on the material’s paths (`CLASSIFIER=deterministic` v1).

| If | Type | Subtype |
| --- | --- | --- |
| Root project marker (`pyproject.toml`, `go.mod`, `package.json`, …) | `project` | language / tool |
| All CSV/TSV | `dataset` | `csv` |
| All PDF | `document` | `pdf` |
| All `.md` / `.txt` / `.rst` | `document` | `markdown` or `text` |
| All code suffixes | `code` | first suffix |
| One packaged artifact | `code` / mapped hint | `python_wheel`, `java_jar`, … |

Unmatched → `unknown`. Discovery hints can already set type; process re-classifies from files.

## Extract (the units)

`extract_units` then `chunk_units` (`EXTRACTOR=extractors` v6). Defaults: cap **20** units per material (`MAX_UNITS_PER_MATERIAL`), window **512** tokens / **64** overlap (`CHUNK_TOKENS` / `CHUNK_OVERLAP_TOKENS`). File bytes capped by `MAX_EXTRACT_BYTES`.

Each unit: `type`, `content`, `location` (path + page or line range or section), `digest`.

| Material | Raw extract | After chunk | Citation looks like |
| --- | --- | --- | --- |
| PDF | One unit per page (`pypdf` text) | `document.pages` windows 512/64 | `paper.pdf page 1` |
| DOCX | Paragraphs / sections | `document.sections` or `document.window` | path + section or lines |
| Markdown / text | File text | Headings then 512/64 | path + lines |
| Dataset | Whole CSV/TSV as `table` (header → `columns`, row count) | `table` windows | path + lines |
| Project | Ranked files, cap 20: identity (2) → config (2) → entry (2) → API (4) → core (5). Skip tests, lockfiles, `docs/`, `node_modules` | Top-level Python / Go / JS symbols → `code.symbol`; else `code.file` | `src/api.py lines 1-2` |
| Packaged artifact | Peek metadata (name, version) | Passthrough, no explode | package id |
| `.xlsx` / `.pptx` / `.doc` | Stub one-liner | Passthrough | filename |
| Binary / installer | Stub + size | Passthrough | filename |

Project ranking prefers `pyproject.toml` / `go.mod` / `main.py` / `index.ts` / `api`/`routes` stems. Documents keep every page, then window. Empty PDF still yields page 1.

## Analyze (not a citation)

`build_profile` picks a coverage mode, then `ANALYZER=deterministic` or `llm`:

| Mode | When |
| --- | --- |
| `direct` | Small enough to read all units |
| `hierarchical` | Long document: leaf digests, then reduce |
| `structural_sample` | Large project: inventory + deep-read a few files |
| `artifact_metadata` | Wheel / JAR: metadata only |

`MaterialAnalysis`: one `title`, one `summary`, `topics`, `keywords`, `technologies`, optional `entities` / `purpose`. LLM uses `LLM_BASE_URL` and falls back to deterministic on failure.

This summary is **material-level**. It is not cited. Units stay the evidence.

## ResearchMaterial + index

`build_research_material` lifts title/summary from analysis (or package name / first text). Metadata can include `topics`, `skipped` paths, `author` / `pages` from PDF, CSV `columns`.

`IndexService.replace` embeds:

1. Each content unit (`unit_text`)
2. One `__material__` point (`material_text`: title + summary + topics)

Same `EMBEDDER` as search. Hop-1 UI search uses material points only. The agent hop-2 uses units and **drops** `__material__`.
