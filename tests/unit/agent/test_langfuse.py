from material_platform.infrastructure.tracing.langfuse_trace import (
    LangfuseTracer,
)
from material_platform.infrastructure.tracing.trace import (
    TeeTracer,
    make_tracer,
    recorded,
)


class _Node:
    def __init__(self, name: str) -> None:
        self.name = name
        self.children: list[_Node] = []
        self.events: list[str] = []
        self.generations: list[str] = []
        self.ended = False

    def span(self, name: str, metadata=None):
        child = _Node(name)
        self.children.append(child)
        return child

    def event(self, name: str, metadata=None) -> None:
        self.events.append(name)

    def generation(self, name: str, input=None, output=None, metadata=None):
        child = _Node(name)
        self.generations.append(name)
        self.children.append(child)
        return child

    def end(self) -> None:
        self.ended = True

    def get_trace_url(self) -> str:
        return "https://cloud.langfuse.com/trace/v2-example"


class _V2:
    def __init__(self) -> None:
        self.root: _Node | None = None
        self.flushed = False

    def trace(self, name: str, session_id=None, user_id=None) -> _Node:
        self.session_id = session_id
        self.user_id = user_id
        self.root = _Node(name)
        return self.root

    def flush(self) -> None:
        self.flushed = True


class _Obs:
    def __init__(self, client: "_V4", name: str, as_type: str) -> None:
        self.name = name
        self.as_type = as_type
        self.input = None
        self.output = None
        self._client = client

    def __enter__(self) -> "_Obs":
        self._client.stack.append(self)
        self._client.opened.append(self)
        return self

    def __exit__(self, *args: object) -> None:
        self._client.stack.pop()

    def update(self, **kwargs: object) -> None:
        if "output" in kwargs:
            self.output = kwargs["output"]
        if "input" in kwargs:
            self.input = kwargs["input"]

    def create_event(self, *, name: str, metadata=None, **kwargs):
        return self._client.create_event(name=name, metadata=metadata, **kwargs)


class _V4:
    def __init__(self) -> None:
        self.stack: list[_Obs] = []
        self.opened: list[_Obs] = []
        self.events: list[str] = []
        self.flushed = False
        self.trace_url = "https://cloud.langfuse.com/trace/v4-example"

    def start_as_current_observation(self, *, as_type: str, name: str, **kwargs):
        if as_type == "event":
            raise AssertionError("v4 rejects as_type=event")
        obs = _Obs(self, name, as_type)
        obs.input = kwargs.get("input")
        return obs

    def create_event(self, *, name: str, metadata=None, **kwargs) -> _Obs:
        self.events.append(name)
        obs = _Obs(self, name, "event")
        self.opened.append(obs)
        return obs

    def get_current_trace_id(self) -> str | None:
        return "v4-trace-id" if self.stack else None

    def get_trace_url(self, *, trace_id: str | None = None) -> str:
        if not trace_id and not self.stack:
            raise RuntimeError("No active span in current context")
        return self.trace_url

    def flush(self) -> None:
        self.flushed = True


def test_langfuse_v2_nests_spans_and_generations() -> None:
    client = _V2()
    tracer = LangfuseTracer(client=client)
    with tracer.span("deep-research", query="handle_request"):
        with tracer.span("plan"):
            tracer.generation("plan", "split questions", '{"ok": true}')
        with tracer.span("retrieve", question_id="Q0"):
            with tracer.span("embed", model="fake", chars=14):
                tracer.set_output({"model": "fake", "chars": 14})
            with tracer.span("hop1", k=5):
                tracer.set_output({"hits": 1, "top": "paper.pdf"})
            with tracer.span("hop2", k=20):
                tracer.set_output({"hits": 1, "top": "paper.pdf page 1"})
            with tracer.span("rerank", enabled=False):
                tracer.set_output({"enabled": False, "docs": 1, "chars": 0})
            tracer.event("select", hits=1, query="handle_request")
    tracer.flush()
    root = client.root
    assert root is not None
    names = [child.name for child in root.children]
    assert names[0] == "deep-research"
    nested = [child.name for child in root.children[0].children]
    assert nested == ["plan", "retrieve"]
    retrieve = root.children[0].children[1]
    assert [child.name for child in retrieve.children] == [
        "embed",
        "hop1",
        "hop2",
        "rerank",
    ]
    assert "plan" in root.children[0].children[0].generations
    assert "select" in root.children[0].children[1].events
    assert tracer.trace_url() == "https://cloud.langfuse.com/trace/v2-example"
    assert client.flushed


def test_langfuse_v4_uses_observations() -> None:
    client = _V4()
    tracer = LangfuseTracer(client=client, session_id="s1")
    with tracer.span("deep-research"):
        with tracer.span("extract", question_id="Q0"):
            tracer.generation("extract", "prompt", "y" * 500)
            tracer.event("extract", added=1)
            tracer.set_output({"added": 1, "findings": ["ok"]})
        tracer.set_output({"text": "ok"})
    kinds = [(item.name, item.as_type) for item in client.opened]
    assert ("deep-research", "span") in kinds
    assert ("extract", "span") in kinds
    assert ("extract", "generation") in kinds
    assert "extract" in client.events
    gen = next(item for item in client.opened if item.as_type == "generation")
    assert gen.input == "prompt"
    assert gen.output == "y" * 500
    tracer.generation("extract", "z" * 40_000, "w" * 40_000)
    huge = [item for item in client.opened if item.as_type == "generation"][-1]
    assert str(huge.input).endswith("…")
    assert len(str(huge.input)) == 32_000
    extract = next(
        item
        for item in client.opened
        if item.name == "extract" and item.as_type == "span"
    )
    assert extract.output == {"added": 1, "findings": ["ok"]}
    root = next(item for item in client.opened if item.name == "deep-research")
    assert root.output == {"text": "ok"}
    assert not client.stack
    assert tracer.trace_url() == "https://cloud.langfuse.com/trace/v4-example"


def test_make_tracer_tees_recording_and_langfuse() -> None:
    client = _V2()
    tracer = make_tracer(recording=True, client=client)
    assert isinstance(tracer, TeeTracer)
    with tracer.span("plan", query="q"):
        tracer.event("plan", questions=1)
        tracer.generation("plan", "p", "{}")
    log = recorded(tracer)
    assert log is not None
    assert [span.name for span in log.spans] == ["plan"]
    assert log.events[0].name == "plan"
    assert log.generations[0].name == "plan"
    assert client.root is not None
    assert tracer.trace_url()


def test_langfuse_v2_sets_user_id() -> None:
    client = _V2()
    tracer = LangfuseTracer(client=client, session_id="s1", user_id="u1")
    assert client.session_id == "s1"
    assert client.user_id == "u1"
    with tracer.span("deep-research"):
        pass
    assert tracer._user_id == "u1"


def test_make_tracer_passes_user_id() -> None:
    client = _V2()
    tracer = make_tracer(client=client, session_id="sid", user_id="uid")
    assert isinstance(tracer, LangfuseTracer)
    assert tracer._user_id == "uid"
    assert client.user_id == "uid"


def test_langfuse_handler_off_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    from material_platform.infrastructure.tracing.langfuse_trace import (
        langfuse_handler,
    )

    assert langfuse_handler() is None
