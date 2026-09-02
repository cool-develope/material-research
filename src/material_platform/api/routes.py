from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from material_platform.agent.models import ResearchReport
from material_platform.agent.service import ResearchAgent
from material_platform.agent.trace import Tracer, make_tracer
from material_platform.analysis import make_llm_client
from material_platform.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from material_platform.application.deep_research import DeepResearchService
from material_platform.application.runtime import Runtime
from material_platform.config import Settings

router = APIRouter()


def _runtime_of(request: Request) -> Runtime:
    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, Runtime):
        raise HTTPException(status_code=503, detail="runtime not configured")
    return runtime


def _tracer_of(settings: Settings, session_id: str) -> Tracer:
    return make_tracer(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        session_id=session_id,
    )


@router.post("/search", response_model=SearchResponse)
def search(request: Request, body: SearchRequest) -> SearchResponse:
    runtime = _runtime_of(request)
    offset = (body.page - 1) * body.page_size
    tracer = _tracer_of(runtime.settings, body.query[:80])
    try:
        with runtime.session() as session:
            page = DeepResearchService(session, runtime.index).search(
                body.query,
                offset=offset,
                limit=body.page_size,
                material_type=body.material_type,
                tracer=tracer,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tracer.flush()
    return SearchResponse(
        query=body.query,
        page=body.page,
        page_size=body.page_size,
        has_more=page.has_more,
        results=[
            SearchHit(
                material_id=hit.material_id,
                title=hit.title,
                material_type=hit.material_type,
                root_path=hit.root_path,
                score=hit.score,
                siblings=list(hit.siblings),
            )
            for hit in page.results
        ],
        trace_url=tracer.trace_url(),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: Request, body: ChatRequest) -> ChatResponse:
    runtime = _runtime_of(request)
    settings = runtime.settings
    mode = body.mode or settings.agent_mode
    tracer = _tracer_of(settings, body.query[:80])
    client = None
    if settings.llm_base_url:
        client = make_llm_client(settings)
    try:
        with runtime.session() as session:
            report = ResearchAgent(
                DeepResearchService(session, runtime.index).select,
                tracer=tracer,
                client=client,
                mode=mode,
            ).ask(body.query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tracer.flush()
    return _chat_response(report, mode=mode, trace_url=tracer.trace_url())


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True)


def _chat_response(
    report: ResearchReport, *, mode: str, trace_url: str | None
) -> ChatResponse:
    return ChatResponse(
        objective=report.objective,
        summary=report.summary,
        text=report.text,
        sections=list(report.sections),
        citations=list(report.citations),
        mode=mode,
        trace_url=trace_url,
    )
