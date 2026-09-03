# Agent flow

Deep Research chat (`POST /chat`). Requires a session cookie. Search hop-1 is **not** this graph; see [System design](system-design.md). Units come from the [pipeline](pipeline.md).

```text
START
  → plan
      ├─ needs retrieval? → retrieve → extract → gap
      │                         ↑              │
      │                         └──────────────┘  while queue and select budget
      │                       → findings → write → validate → END
      └─ no retrieval ──────────────────────────→ write → validate → END
```

Continue on the same `thread_id` runs **compact** first (fold prior turns), then the same graph.

## Budgets

`AGENT_MODE` or request `mode`. Hop-1 / hop-2 sizes stay **5 / 20**.

| Mode | Plan questions | Select calls | Units / material | Evidence / question | Evidence total |
| --- | --- | --- | --- | --- | --- |
| `quick` | 2 | 3 | 3 | 8 | 24 |
| `standard` | 6 | 8 | 5 | 20 | 80 |
| `deep` | 8 | 16 | 5 | 20 | 160 |

## Nodes

| Node | Input | Does | Output |
| --- | --- | --- | --- |
| **compact** | Prior `AgentState` + new query | LLM (or rule) fold of conversation into a working set | New state; not the stored transcript |
| **plan** | Query + compact context | LLM plan: objective + questions. Fallback: the query as one question | `ResearchPlan`, queue of `(question_id, query)` |
| **retrieve** | Next queue item | `DeepResearch.select`: hop-1 materials (5) → hop-2 units (20) → drop `__material__` → optional rerank → same-source boost → diversity cap | `pending` citations |
| **extract** | Pending hits + question | LLM turns snippets into `EvidenceItem` (finding, stance). Fallback: use the snippet | Evidence, capped per question and total |
| **gap** | Evidence so far | Mark questions covered / gap. LLM may enqueue follow-up queries | Queue extras, or empty |
| **findings** | Evidence grouped by question | One `Finding` per question: claim, supporting / contradicting ids | `state.findings` |
| **write** | Findings + evidence | One section per question (LLM rewrite if `LLM_BASE_URL` set) | `ResearchReport` + citation list |
| **validate** | Report | Drop findings/citations without a real unit locator. Never keep `__material__` or empty locators | Clean report |

`needs_retrieval` false (follow-up that the planner can answer from prior research) skips retrieve / extract / gap / findings and goes to write.

## Retrieve (select)

Only this path runs hop-2.

```text
query
  → hop 1   level=material          top 5
  → hop 2   level=content_unit
            AND material_id IN …    top 20
  → drop __material__
  → rerank if RERANKER is on
  → same-source boost
  → diversity: budgets.units_per_material per material
  → Citation
```

A citation is `paper.pdf page 1` or `src/api.py lines 1-2`. UI search never does this hop.

## What the user sees

The API stores the **full** thread. The graph plans from the **compact** working set. Langfuse gets `user_id` and `session_id` (thread id) when keys are set.

Report text is sectioned by plan questions. Validate can replace a section with `No evidence retrieved.` if every citation was dropped.

## What the agent does not do

| Work | Where |
| --- | --- |
| Discover / extract / embed a zip | [Pipeline](pipeline.md) + Dagster |
| Hop-1 SERP for the UI | `POST /search` |
| Auth / thread list | FastAPI |
| Host embed / LLM | [Inference](inference.md) |
