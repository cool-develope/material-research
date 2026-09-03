from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from material_platform.agent.models import ResearchReport
from material_platform.agent.service import ResearchAgent
from material_platform.agent.trace import Tracer, make_tracer
from material_platform.analysis import make_llm_client
from material_platform.api.schemas import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ChatThreadListResponse,
    ChatThreadSummary,
    HealthResponse,
    MaterialDetailResponse,
    MaterialUnitHit,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from material_platform.application.chat_history import ChatHistoryService
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
            page = DeepResearchService(
                session, runtime.index, runtime.store
            ).search(
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
        page_count=page.page_count,
        total=page.total,
        results=[
            SearchHit(
                material_id=hit.material_id,
                title=hit.title,
                material_type=hit.material_type,
                root_path=hit.root_path,
                score=hit.score,
                snippet=hit.snippet,
                keywords=list(hit.keywords),
            )
            for hit in page.results
        ],
        trace_url=tracer.trace_url(),
    )


@router.get("/materials/{material_id}", response_model=MaterialDetailResponse)
def material_detail(request: Request, material_id: UUID) -> MaterialDetailResponse:
    runtime = _runtime_of(request)
    with runtime.session() as session:
        detail = DeepResearchService(
            session, runtime.index, runtime.store
        ).get_material(material_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="material not found")
    return MaterialDetailResponse(
        material_id=detail.material_id,
        title=detail.title,
        material_type=detail.material_type,
        material_subtype=detail.material_subtype,
        root_path=detail.root_path,
        status=detail.status,
        summary=detail.summary,
        purpose=detail.purpose,
        keywords=list(detail.keywords),
        topics=list(detail.topics),
        technologies=list(detail.technologies),
        research_relevance=detail.research_relevance,
        units=[
            MaterialUnitHit(unit_type=item.unit_type, citation=item.citation)
            for item in detail.units
        ],
    )


@router.get("/chats", response_model=ChatThreadListResponse)
def chat_threads(request: Request) -> ChatThreadListResponse:
    runtime = _runtime_of(request)
    with runtime.session() as session:
        threads = ChatHistoryService(session).list_threads()
    return ChatThreadListResponse(
        threads=[
            ChatThreadSummary(
                thread_id=item.thread_id,
                title=item.title,
                mode=item.mode,
                updated_at=item.updated_at.isoformat(),
                messages=item.messages,
            )
            for item in threads
        ]
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: Request, body: ChatRequest) -> ChatResponse:
    runtime = _runtime_of(request)
    settings = runtime.settings
    mode = body.mode or settings.agent_mode
    tracer = _tracer_of(settings, body.thread_id or body.query[:80])
    client = None
    if settings.llm_base_url:
        client = make_llm_client(settings)
    try:
        with runtime.session() as session:
            history = ChatHistoryService(session)
            prior_turns = (
                history.compact_turns(body.thread_id) if body.thread_id else []
            )
            agent = ResearchAgent(
                DeepResearchService(session, runtime.index).select,
                tracer=tracer,
                client=client,
                mode=mode,
                checkpointer=runtime.checkpointer,
                store=runtime.memory_store,
            )
            report = agent.ask(
                body.query,
                thread_id=body.thread_id,
                prior_turns=prior_turns or None,
            )
            thread_id = agent.last_thread_id
            history.record_turn(
                thread_id,
                query=body.query,
                report=report,
                mode=mode,
            )
        return _chat_response(
            report,
            mode=mode,
            thread_id=thread_id,
            trace_url=tracer.trace_url(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tracer.flush()


@router.get("/chat/{thread_id}", response_model=ChatHistoryResponse)
def chat_history(request: Request, thread_id: str) -> ChatHistoryResponse:
    runtime = _runtime_of(request)
    with runtime.session() as session:
        thread = ChatHistoryService(session).get(thread_id.strip())
    if thread is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return ChatHistoryResponse(
        thread_id=thread.thread_id,
        mode=thread.mode,
        messages=[
            ChatHistoryMessage(
                role=item.role,
                content=item.content,
                summary=item.summary,
                created_at=item.created_at.isoformat(),
                ordinal=item.ordinal,
            )
            for item in thread.messages
        ],
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True)


def _chat_response(
    report: ResearchReport,
    *,
    mode: str,
    thread_id: str,
    trace_url: str | None,
) -> ChatResponse:
    return ChatResponse(
        objective=report.objective,
        summary=report.summary,
        text=report.text,
        sections=list(report.sections),
        citations=list(report.citations),
        mode=mode,
        thread_id=thread_id,
        trace_url=trace_url,
    )
