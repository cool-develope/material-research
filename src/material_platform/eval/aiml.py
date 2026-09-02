from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from material_platform.agent.service import ResearchAgent
from material_platform.agent.trace import make_tracer
from material_platform.analysis import make_llm_client
from material_platform.application.deep_research import DeepResearchService
from material_platform.application.local import ingest_and_process, sqlite_settings
from material_platform.application.runtime import Runtime
from material_platform.config import Settings
from material_platform.eval import (
    LEXICAL,
    SEMANTIC,
    format_report,
    hit_at_1,
    matches,
)
from material_platform.eval.aiml_checks import (
    citation_errors,
    format_errors,
    ingest_errors,
)
from material_platform.eval.aiml_corpus import (
    AIML_ZIP,
    REQUIRED_LEXICAL_IDS,
    agent_cases,
    make_suite,
)
from material_platform.eval.aiml_fetch import build_aiml_zip
from material_platform.eval.cases import EvalSuite
from material_platform.eval.experiment import score_settings
from material_platform.eval.prod import (
    AIML_COLLECTION,
    ARCHIVE_TIMEOUT,
    EXTRACT_BYTES,
    REPO,
    apply_prod_knobs,
    migrate_head,
    preflight_prod,
    prod_env,
    wipe_index,
)

_REQUIRED_AGENT = frozenset({"agent-qlora"})
_LOCAL_DATA = Path("/tmp/mp-aiml")
_PROD_DATA = Path("/tmp/mp-aiml-prod")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mp eval-aiml",
        description="Download public AI/ML sources into a local zip, then "
        "ingest and score discovery / retrieval / agent citations.",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Download and zip sources; do not ingest.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Use an existing tests/fixtures/eval_aiml/research.zip.",
    )
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument(
        "--lexical-only",
        action="store_true",
        help="Skip semantic retrieve cases (they need BGE-M3).",
    )
    parser.add_argument("--skip-agent", action="store_true")
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Compose stack: Postgres, MinIO, Qdrant, BGE-M3, reranker, "
        "LLM analysis, Langfuse. Ignores EMBEDDER/RERANKER/ANALYZER in .env.",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Score an existing ingest (same --data-dir / compose collection).",
    )
    args = parser.parse_args(argv)

    zip_path = AIML_ZIP
    if not args.skip_ingest and not args.skip_build:
        zip_path = build_aiml_zip()
        print(f"wrote {zip_path}", flush=True)
    elif not args.skip_ingest and not zip_path.is_file():
        print(f"zip not found: {zip_path}", file=sys.stderr)
        return 1
    if args.build_only:
        return 0

    data_dir = (args.data_dir or (_PROD_DATA if args.prod else _LOCAL_DATA)).resolve()
    if args.prod:
        settings, env_errors = _prod_settings(data_dir, zip_path, args.skip_ingest)
        if env_errors:
            for item in env_errors:
                print(item, file=sys.stderr)
            return 1
        os.chdir(REPO)
        migrate_head()
        if not args.skip_ingest:
            wipe_index(settings)
    else:
        settings = _eval_settings(data_dir)

    print(
        f"{'skip ingest' if args.skip_ingest else 'ingesting'} "
        f"{zip_path} -> {data_dir}  "
        f"analyzer={settings.analyzer} embedder={settings.embedder} "
        f"reranker={settings.reranker} collection={settings.qdrant_collection}",
        flush=True,
    )
    errors: tuple[str, ...] = ()
    if not args.skip_ingest:
        run = ingest_and_process(
            zip_path, settings, process=True, strict=False, progress=True
        )
        print(f"materials={run.materials} units={run.units}", flush=True)
        errors = ingest_errors(run)
        print(format_errors(errors, heading="corpus"), end="")

    suite = _load_suite()
    retrieve = score_settings(settings, suite, lexical_only=args.lexical_only)
    report = format_report(retrieve)
    report_path = data_dir / "eval_aiml_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"wrote {report_path}", flush=True)
    required_miss = [
        scored
        for scored in retrieve.cases
        if scored.mode == LEXICAL
        and scored.case_id in REQUIRED_LEXICAL_IDS
        and not scored.hit_at_1
    ]
    if required_miss:
        print("required lexical misses:", flush=True)
        for scored in required_miss:
            print(f"  {scored.case_id}  {scored.citations[:1]}", flush=True)

    agent_errors: list[str] = []
    if not args.skip_agent:
        agent_errors.extend(_score_agent(settings, prod=args.prod))
    if agent_errors:
        print(format_errors(tuple(agent_errors), heading="agent"), end="")

    lex_ok, lex_n = hit_at_1(retrieve, LEXICAL)
    sem_ok, sem_n = hit_at_1(retrieve, SEMANTIC)
    print(
        f"lexical required "
        f"{len(REQUIRED_LEXICAL_IDS) - len(required_miss)}/"
        f"{len(REQUIRED_LEXICAL_IDS)}"
    )
    print(f"lexical all {lex_ok}/{lex_n}")
    if sem_n:
        print(f"semantic {sem_ok}/{sem_n}")
    if errors or required_miss or agent_errors:
        return 1
    return 0


def _score_agent(settings: Settings, *, prod: bool) -> list[str]:
    client = None
    if prod:
        if not settings.llm_base_url:
            return ["LLM_BASE_URL required for --prod agent"]
        client = make_llm_client(settings)
    errors: list[str] = []
    runtime = Runtime(settings)
    with runtime.session() as session:
        select = DeepResearchService(session, runtime.index).select
        for case in agent_cases():
            tracer = make_tracer(
                public_key=settings.langfuse_public_key if prod else None,
                secret_key=settings.langfuse_secret_key if prod else None,
                host=settings.langfuse_host,
                session_id=case.id,
            )
            agent = ResearchAgent(
                select,
                tracer=tracer,
                client=client,
                mode=settings.agent_mode if prod else "quick",
            )
            report = agent.ask(case.query)
            tracer.flush()
            url = tracer.trace_url()
            if url:
                print(f"langfuse {case.id}: {url}", flush=True)
            banned = citation_errors(report.citations)
            errors.extend(banned)
            hit = any(
                matches(item, expected)
                for expected in case.expect
                for item in report.citations
            )
            if not hit and case.id in _REQUIRED_AGENT:
                got = [item.citation for item in report.citations[:3]]
                errors.append(f"{case.id} expected {case.expect[0].path}, got {got}")
            elif not hit:
                print(f"agent probe miss {case.id}", flush=True)
    return errors


def _prod_settings(
    data_dir: Path, source: Path, skip_ingest: bool
) -> tuple[Settings, list[str]]:
    data_dir.mkdir(parents=True, exist_ok=True)
    settings = apply_prod_knobs(
        Settings().model_copy(update={"workspace_root": data_dir}),
        collection=AIML_COLLECTION,
    )
    env = prod_env(settings, collection=AIML_COLLECTION)
    errors = preflight_prod(settings, env, source=source, skip_ingest=skip_ingest)
    return settings, errors


def _eval_settings(data_dir: Path) -> Settings:
    settings = sqlite_settings(Settings(), data_dir)
    return settings.model_copy(
        update={
            "max_extract_bytes": max(settings.max_extract_bytes, EXTRACT_BYTES),
            "max_archive_timeout_seconds": max(
                settings.max_archive_timeout_seconds, ARCHIVE_TIMEOUT
            ),
            "embedder": "fake",
            "reranker": "off",
            "analyzer": "deterministic",
        }
    )


def _load_suite() -> EvalSuite:
    return make_suite()
