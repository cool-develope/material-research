# Docs

Material Platform discovers independent research materials from files, directories, and ZIP archives, then processes each one into a `ResearchMaterial` for search and Deep Research.

| Doc | What it covers |
| --- | --- |
| [Architecture](architecture.md) | Layers, ownership, and how requests flow |
| [System design](system-design.md) | Ingest, process, search, chat, and auth |
| [Pipeline](pipeline.md) | What we extract and how it is indexed |
| [Agent](agent.md) | Deep Research graph, retrieve, evidence |
| [Project structure](structure.md) | Packages, services, and files |
| [Setup](setup.md) | Local sqlite and compose spin-up |
| [Environment](environment.md) | Env vars and how they relate |
| [Dagster](dagster.md) | Jobs, sensors, inbox folder, pools |
| [Inbox](inbox.md) | Source drop, first run, what we do not keep |
| [Inference](inference.md) | Local BGE vs HTTP embed / rerank / LLM |
| [Todos](todos.md) | Open follow-ups |
| [Air-gap](airgap.md) | Offline bundle: wheels, web, images, kubeadm debs, Dagster Helm |

Start at [Setup](setup.md). Copy `.env.example` to `.env` before using Postgres, MinIO, or Langfuse.
