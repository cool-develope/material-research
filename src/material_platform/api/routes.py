from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from material_platform.agent.service import ResearchAgent
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
    SignInRequest,
    SignUpRequest,
    UserResponse,
)
from material_platform.application.auth import AuthError, AuthService
from material_platform.application.chat_history import (
    ChatHistoryService,
    ThreadAccessError,
)
from material_platform.application.deep_research import DeepResearchService
from material_platform.application.runtime import Runtime
from material_platform.config import Settings
from material_platform.domain.research import ResearchReport
from material_platform.infrastructure.database.auth import StoredUser
from material_platform.infrastructure.tracing.trace import Tracer, make_tracer

router = APIRouter()

SESSION_COOKIE = "mp_session"
_SESSION_MAX_AGE = 30 * 24 * 3600


def _runtime_of(request: Request) -> Runtime:
    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, Runtime):
        raise HTTPException(status_code=503, detail="runtime not configured")
    return runtime


def _current_user(request: Request, session) -> StoredUser | None:
    return AuthService(session).user_for_token(request.cookies.get(SESSION_COOKIE))


def _user_id_of(user: StoredUser | None) -> UUID | None:
    return None if user is None else user.user_id


def _tracer_of(
    settings: Settings,
    session_id: str,
    *,
    user_id: str | None = None,
) -> Tracer:
    return make_tracer(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        session_id=session_id,
        user_id=user_id,
    )


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=_SESSION_MAX_AGE,
        path="/",
    )


def _user_response(user: StoredUser) -> UserResponse:
    return UserResponse(user_id=user.user_id, name=user.name, email=user.email)


@router.post("/auth/signup", response_model=UserResponse)
def signup(request: Request, body: SignUpRequest, response: Response) -> UserResponse:
    runtime = _runtime_of(request)
    try:
        with runtime.session() as session:
            user, token = AuthService(session).signup(
                name=body.name, email=body.email, password=body.password
            )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    _set_session_cookie(response, token, runtime.settings)
    return _user_response(user)


@router.post("/auth/signin", response_model=UserResponse)
def signin(request: Request, body: SignInRequest, response: Response) -> UserResponse:
    runtime = _runtime_of(request)
    try:
        with runtime.session() as session:
            user, token = AuthService(session).signin(
                email=body.email, password=body.password
            )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    _set_session_cookie(response, token, runtime.settings)
    return _user_response(user)


@router.post("/auth/signout")
def signout(request: Request, response: Response) -> dict[str, bool]:
    runtime = _runtime_of(request)
    with runtime.session() as session:
        AuthService(session).signout(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me", response_model=UserResponse)
def me(request: Request) -> UserResponse:
    runtime = _runtime_of(request)
    with runtime.session() as session:
        user = _current_user(request, session)
    if user is None:
        raise HTTPException(status_code=401, detail="not signed in")
    return _user_response(user)


@router.post("/search", response_model=SearchResponse)
def search(request: Request, body: SearchRequest) -> SearchResponse:
    runtime = _runtime_of(request)
    tracer: Tracer | None = None
    try:
        with runtime.session() as session:
            user = _current_user(request, session)
            tracer = _tracer_of(
                runtime.settings,
                body.query[:80],
                user_id=None if user is None else str(user.user_id),
            )
            page = DeepResearchService(
                session, runtime.index, runtime.store
            ).search(
                body.query,
                offset=(body.page - 1) * body.page_size,
                limit=body.page_size,
                material_type=body.material_type,
                tracer=tracer,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if tracer is not None:
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
        trace_url=tracer.trace_url() if tracer is not None else None,
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
        user = _current_user(request, session)
        threads = ChatHistoryService(session).list_threads(user_id=_user_id_of(user))
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
    tracer: Tracer | None = None
    client = None
    if settings.llm_base_url:
        client = make_llm_client(settings)
    try:
        with runtime.session() as session:
            user = _current_user(request, session)
            if user is None:
                raise HTTPException(status_code=401, detail="sign in required")
            user_id = user.user_id
            history = ChatHistoryService(session)
            if body.thread_id is not None:
                existing = history.get(body.thread_id, user_id=user_id)
                if existing is None:
                    raise HTTPException(status_code=404, detail="thread not found")
            tracer = _tracer_of(
                settings,
                body.thread_id or body.query[:80],
                user_id=None if user is None else str(user.user_id),
            )
            prior_turns = (
                history.compact_turns(body.thread_id, user_id=user_id)
                if body.thread_id
                else []
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
                user_id=user_id,
            )
        return _chat_response(
            report,
            mode=mode,
            thread_id=thread_id,
            trace_url=tracer.trace_url(),
        )
    except ThreadAccessError as exc:
        raise HTTPException(status_code=404, detail="thread not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if tracer is not None:
            tracer.flush()


@router.get("/chat/{thread_id}", response_model=ChatHistoryResponse)
def chat_history(request: Request, thread_id: str) -> ChatHistoryResponse:
    runtime = _runtime_of(request)
    with runtime.session() as session:
        user = _current_user(request, session)
        if user is None:
            raise HTTPException(status_code=401, detail="sign in required")
        thread = ChatHistoryService(session).get(
            thread_id.strip(), user_id=user.user_id
        )
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
