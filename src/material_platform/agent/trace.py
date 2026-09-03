from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass

_CLIP = 400
_CLIP_LLM = 32_000


@dataclass
class SpanEvent:
    name: str
    attrs: dict[str, object]


class Tracer:
    def span(self, name: str, **attrs: object) -> AbstractContextManager[None]:
        raise NotImplementedError

    def event(self, name: str, **attrs: object) -> None:
        return None

    def generation(
        self, name: str, prompt: str, output: str, **attrs: object
    ) -> None:
        return None

    def flush(self) -> None:
        return None

    def set_output(self, value: object) -> None:
        return None

    def set_input(self, value: object) -> None:
        return None

    def trace_url(self) -> str | None:
        return None


class NoOpTracer(Tracer):
    @contextmanager
    def span(self, name: str, **attrs: object) -> Iterator[None]:
        yield


class RecordingTracer(Tracer):
    def __init__(self) -> None:
        self.spans: list[SpanEvent] = []
        self.events: list[SpanEvent] = []
        self.generations: list[SpanEvent] = []
        self._stack: list[SpanEvent] = []

    @contextmanager
    def span(self, name: str, **attrs: object) -> Iterator[None]:
        event = SpanEvent(name=name, attrs=dict(attrs))
        self.spans.append(event)
        self._stack.append(event)
        try:
            yield
        finally:
            self._stack.pop()

    def event(self, name: str, **attrs: object) -> None:
        self.events.append(SpanEvent(name=name, attrs=dict(attrs)))

    def generation(
        self, name: str, prompt: str, output: str, **attrs: object
    ) -> None:
        payload = dict(attrs)
        payload["prompt"] = clip_llm(prompt)
        payload["output"] = clip_llm(output)
        self.generations.append(SpanEvent(name=name, attrs=payload))

    def set_output(self, value: object) -> None:
        if self._stack:
            self._stack[-1].attrs["output"] = value

    def set_input(self, value: object) -> None:
        if self._stack:
            self._stack[-1].attrs["input"] = value


class TeeTracer(Tracer):
    def __init__(self, *inners: Tracer) -> None:
        self.inners = inners

    @contextmanager
    def span(self, name: str, **attrs: object) -> Iterator[None]:
        with ExitStack() as stack:
            for inner in self.inners:
                stack.enter_context(inner.span(name, **attrs))
            yield

    def event(self, name: str, **attrs: object) -> None:
        for inner in self.inners:
            inner.event(name, **attrs)

    def generation(
        self, name: str, prompt: str, output: str, **attrs: object
    ) -> None:
        for inner in self.inners:
            inner.generation(name, prompt, output, **attrs)

    def flush(self) -> None:
        for inner in self.inners:
            inner.flush()

    def set_output(self, value: object) -> None:
        for inner in self.inners:
            inner.set_output(value)

    def set_input(self, value: object) -> None:
        for inner in self.inners:
            inner.set_input(value)

    def trace_url(self) -> str | None:
        for inner in self.inners:
            url = inner.trace_url()
            if url:
                return url
        return None


def recorded(tracer: Tracer) -> RecordingTracer | None:
    if isinstance(tracer, RecordingTracer):
        return tracer
    if isinstance(tracer, TeeTracer):
        for inner in tracer.inners:
            found = recorded(inner)
            if found is not None:
                return found
    return None


def make_tracer(
    *,
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str = "https://cloud.langfuse.com",
    session_id: str | None = None,
    user_id: str | None = None,
    recording: bool = False,
    client: object | None = None,
) -> Tracer:
    backend: Tracer | None = None
    if client is not None or (public_key and secret_key):
        try:
            from material_platform.agent.langfuse_trace import LangfuseTracer

            backend = LangfuseTracer(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
                session_id=session_id,
                user_id=user_id,
                client=client,
            )
        except Exception:
            backend = None
    record = RecordingTracer() if recording else None
    if record is not None and backend is not None:
        return TeeTracer(record, backend)
    return record or backend or NoOpTracer()


def clip(text: str) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= _CLIP:
        return stripped
    return stripped[: _CLIP - 1] + "…"


def clip_llm(text: str, *, limit: int = _CLIP_LLM) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def meta(attrs: dict[str, object]) -> dict[str, str | int | float | bool]:
    out: dict[str, str | int | float | bool] = {}
    for key, value in attrs.items():
        if isinstance(value, bool):
            out[key] = value
        elif isinstance(value, int) and not isinstance(value, bool):
            out[key] = value
        elif isinstance(value, float):
            out[key] = value
        elif value is None:
            continue
        else:
            out[key] = clip(str(value))
    return out
