from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.agent.service import ResearchAgent
from material_platform.analysis import make_llm_client
from material_platform.application.chat_history import ChatHistoryService
from material_platform.application.deep_research import DeepResearchService
from material_platform.application.local import sqlite_settings
from material_platform.application.runtime import Runtime
from material_platform.config import Settings
from material_platform.infrastructure.tracing.trace import make_tracer, recorded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mp chat",
        description="Deep Research: plan questions, retrieve, write a cited report.",
    )
    parser.add_argument("query")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM_BASE_URL for plan/extract/write (pytest stays off).",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Print span names. Langfuse is attached when keys are set.",
    )
    parser.add_argument(
        "--mode",
        choices=("quick", "standard", "deep"),
        default=None,
        help="Agent budget: quick=3 selects, standard=8, deep=16. Hop 1/2 stay 5/20.",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Continue a previous chat. Omit to start a new thread.",
    )
    args = parser.parse_args(argv)
    settings = Settings()
    if not args.postgres:
        data_dir = (args.data_dir or settings.workspace_root).resolve()
        db_path = data_dir / "material.db"
        if not db_path.exists():
            print(f"database not found: {db_path}", file=sys.stderr)
            return 1
        settings = sqlite_settings(settings, data_dir)

    tracer = make_tracer(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        recording=args.trace,
        session_id=args.thread_id or args.query[:80],
    )
    client = None
    if args.llm:
        if not settings.llm_base_url:
            print("LLM_BASE_URL required for --llm", file=sys.stderr)
            return 1
        client = make_llm_client(settings)
    runtime = Runtime(settings)
    with runtime.session() as session:
        select = DeepResearchService(session, runtime.index).select
        agent = ResearchAgent(
            select,
            tracer=tracer,
            client=client,
            mode=args.mode or settings.agent_mode,
            checkpointer=runtime.checkpointer,
            store=runtime.memory_store,
        )
        report = agent.ask(args.query, thread_id=args.thread_id)
        ChatHistoryService(session).record_turn(
            agent.last_thread_id,
            query=args.query,
            report=report,
            mode=args.mode or settings.agent_mode,
        )
    sys.stdout.write(report.text)
    print(f"thread: {agent.last_thread_id}", file=sys.stderr)
    log = recorded(tracer)
    if args.trace and log is not None:
        print("--- spans ---", file=sys.stderr)
        for span in log.spans:
            print(span.name, file=sys.stderr)
        print("--- generations ---", file=sys.stderr)
        for gen in log.generations:
            print(gen.name, file=sys.stderr)
    tracer.flush()
    url = tracer.trace_url()
    if url:
        print(f"langfuse: {url}", file=sys.stderr)
    return 0
