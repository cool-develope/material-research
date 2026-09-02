from __future__ import annotations

from pathlib import Path

from material_platform.application.deep_research import DeepResearchService
from material_platform.application.local import ingest_and_process, sqlite_settings
from material_platform.application.runtime import Runtime
from material_platform.config import Settings
from material_platform.domain.base import Contract
from material_platform.eval.cases import LEXICAL, SEMANTIC, EvalSuite
from material_platform.eval.score import (
    SuiteScore,
    hit_at_1,
    mrr,
    score_suite,
)


class ExperimentRun(Contract):
    label: str
    chunk_tokens: int
    materials: int
    units: int
    score: SuiteScore


def parse_chunk_sweep(text: str) -> tuple[int, ...]:
    key, sep, raw = text.partition("=")
    if sep == "" or key.strip() != "chunk_tokens":
        raise ValueError("sweep must look like chunk_tokens=256,512,1024")
    values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("sweep needs at least one chunk_tokens value")
    if any(value < 1 for value in values):
        raise ValueError("chunk_tokens must be >= 1")
    return values


def score_settings(
    settings: Settings,
    suite: EvalSuite,
    *,
    lexical_only: bool = False,
) -> SuiteScore:
    modes = (LEXICAL,) if lexical_only else None
    runtime = Runtime(settings)
    with runtime.session() as session:
        return score_suite(
            suite,
            DeepResearchService(session, runtime.index).select,
            modes=modes,
        )


def run_chunk_sweep(
    source: Path,
    suite: EvalSuite,
    values: tuple[int, ...],
    *,
    work_dir: Path,
    settings: Settings,
    lexical_only: bool = False,
) -> tuple[ExperimentRun, ...]:
    runs: list[ExperimentRun] = []
    for size in values:
        data_dir = work_dir / f"chunk_tokens-{size}"
        run_settings = sqlite_settings(
            settings.model_copy(update={"chunk_tokens": size}), data_dir
        )
        ingested = ingest_and_process(source, run_settings, process=True)
        score = score_settings(run_settings, suite, lexical_only=lexical_only)
        runs.append(
            ExperimentRun(
                label=f"chunk_tokens={size}",
                chunk_tokens=size,
                materials=ingested.materials,
                units=ingested.units,
                score=score,
            )
        )
    return tuple(runs)


def format_compare(runs: tuple[ExperimentRun, ...]) -> str:
    lines = [
        f"{'knob':<22} {'units':>5} {'lex@1':>8} {'sem@1':>8} {'mrr':>6}",
        "-" * 52,
    ]
    for run in runs:
        lex_ok, lex_n = hit_at_1(run.score, LEXICAL)
        sem_ok, sem_n = hit_at_1(run.score, SEMANTIC)
        lex = f"{lex_ok}/{lex_n}"
        sem = f"{sem_ok}/{sem_n}"
        lines.append(
            f"{run.label:<22} {run.units:>5} {lex:>8} {sem:>8} {mrr(run.score):>6.3f}"
        )
    return "\n".join(lines) + "\n"
