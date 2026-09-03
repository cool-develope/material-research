from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from material_platform.agent.trace import Tracer, clip_llm, meta


class LangfuseTracer(Tracer):
    """Langfuse adapter for SDK v2 (`trace`), v3 (`start_as_current_span`),
    and v4 (`start_as_current_observation`). Nested node spans; LLM calls
    are generations with full prompts and replies. Retrieve outputs are
    locators and scores, not unit bodies.
    """

    def __init__(
        self,
        *,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str = "https://cloud.langfuse.com",
        session_id: str | None = None,
        user_id: str | None = None,
        client: object | None = None,
    ) -> None:
        self._client = client if client is not None else _connect(
            public_key, secret_key, host
        )
        self._kind = _kind(self._client)
        self._session_id = session_id
        self._user_id = user_id
        self._stack: list[Any] = []
        self._trace: Any = None
        self._trace_id: str | None = None
        self._url: str | None = None
        if self._kind == "trace":
            kwargs: dict[str, object] = {"name": "deep-research"}
            if session_id:
                kwargs["session_id"] = session_id
            if user_id:
                kwargs["user_id"] = user_id
            self._trace = self._client.trace(**kwargs)

    @contextmanager
    def span(self, name: str, **attrs: object) -> Iterator[None]:
        payload = meta(attrs)
        if self._session_id:
            payload.setdefault("session_id", self._session_id)
        if self._user_id:
            payload.setdefault("user_id", self._user_id)
        if self._kind == "observation":
            ctx = self._client.start_as_current_observation(
                as_type="span", name=name, metadata=payload, input=payload
            )
            with ctx as obs:
                self._stack.append(obs)
                self._remember()
                self._apply_identity()
                try:
                    yield
                finally:
                    self._stack.pop()
            return
        if self._kind == "span":
            ctx = self._client.start_as_current_span(name=name, metadata=payload)
            with ctx as obs:
                self._stack.append(obs)
                self._remember()
                self._apply_identity()
                try:
                    yield
                finally:
                    self._stack.pop()
            return
        parent = self._stack[-1] if self._stack else self._trace
        child = parent.span(name=name, metadata=payload)
        self._stack.append(child)
        try:
            yield
        finally:
            if hasattr(child, "end"):
                child.end()
            self._stack.pop()

    def event(self, name: str, **attrs: object) -> None:
        payload = meta(attrs)
        current = self._stack[-1] if self._stack else self._trace
        if _emit_event(current, name, payload):
            return
        _emit_event(self._client, name, payload)

    def set_output(self, value: object) -> None:
        current = self._stack[-1] if self._stack else self._trace
        update = getattr(current, "update", None)
        if callable(update):
            update(output=value)

    def set_input(self, value: object) -> None:
        current = self._stack[-1] if self._stack else self._trace
        update = getattr(current, "update", None)
        if callable(update):
            update(input=value)

    def generation(
        self, name: str, prompt: str, output: str, **attrs: object
    ) -> None:
        payload = meta(attrs)
        clipped_in, clipped_out = clip_llm(prompt), clip_llm(output)
        if self._kind == "observation":
            ctx = self._client.start_as_current_observation(
                as_type="generation",
                name=name,
                input=clipped_in,
                metadata=payload,
            )
            with ctx as gen:
                if hasattr(gen, "update"):
                    gen.update(output=clipped_out)
            return
        if self._kind == "span" and hasattr(
            self._client, "start_as_current_generation"
        ):
            ctx = self._client.start_as_current_generation(
                name=name, input=clipped_in, metadata=payload
            )
            with ctx as gen:
                if hasattr(gen, "update"):
                    gen.update(output=clipped_out)
            return
        parent = self._stack[-1] if self._stack else self._trace
        gen = parent.generation(
            name=name, input=clipped_in, output=clipped_out, metadata=payload
        )
        if hasattr(gen, "end"):
            gen.end()

    def flush(self) -> None:
        flush = getattr(self._client, "flush", None)
        if callable(flush):
            flush()

    def trace_url(self) -> str | None:
        if self._url:
            return self._url
        url = _url_of(self._client, trace_id=self._trace_id) or _url_of(
            self._trace, trace_id=self._trace_id
        )
        if url:
            self._url = url
        return url

    def _apply_identity(self) -> None:
        update = getattr(self._client, "update_current_trace", None)
        if not callable(update):
            return
        payload: dict[str, str] = {}
        if self._session_id:
            payload["session_id"] = self._session_id
        if self._user_id:
            payload["user_id"] = self._user_id
        if not payload:
            return
        try:
            update(**payload)
        except TypeError:
            return

    def _remember(self) -> None:
        get_id = getattr(self._client, "get_current_trace_id", None)
        if callable(get_id) and not self._trace_id:
            try:
                value = get_id()
            except Exception:
                value = None
            if isinstance(value, str) and value:
                self._trace_id = value
        if self._url:
            return
        url = _url_of(self._client, trace_id=self._trace_id)
        if not url:
            current = self._stack[-1] if self._stack else self._trace
            url = _url_of(current, trace_id=self._trace_id)
        if url:
            self._url = url


def langfuse_handler(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
) -> object | None:
    """Official LangGraph/LangChain callback. None when keys are unset."""
    import os

    if not os.environ.get("LANGFUSE_PUBLIC_KEY") or not os.environ.get(
        "LANGFUSE_SECRET_KEY"
    ):
        return None
    try:
        from langfuse.langchain import CallbackHandler
    except ImportError:
        try:
            from langfuse.callback import CallbackHandler
        except ImportError:
            return None
    kwargs: dict[str, str] = {}
    if session_id:
        kwargs["session_id"] = session_id
    if user_id:
        kwargs["user_id"] = user_id
    try:
        return CallbackHandler(**kwargs)
    except TypeError:
        try:
            return CallbackHandler()
        except Exception:
            return None
    except Exception:
        return None


def _kind(client: object) -> str:
    if callable(getattr(client, "start_as_current_observation", None)):
        return "observation"
    if callable(getattr(client, "start_as_current_span", None)):
        return "span"
    if callable(getattr(client, "trace", None)):
        return "trace"
    raise TypeError("langfuse client has no span API")


def _connect(public_key: str | None, secret_key: str | None, host: str) -> object:
    from langfuse import Langfuse

    if not public_key or not secret_key:
        raise ValueError("langfuse keys required")
    try:
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            base_url=host,
        )
    except TypeError:
        try:
            return Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        except TypeError:
            return Langfuse(
                public_key=public_key, secret_key=secret_key, base_url=host
            )


def _emit_event(target: object, name: str, payload: dict[str, object]) -> bool:
    if target is None:
        return False
    create = getattr(target, "create_event", None)
    if callable(create):
        create(name=name, metadata=payload, input=payload)
        return True
    emit = getattr(target, "event", None)
    if callable(emit):
        emit(name=name, metadata=payload)
        return True
    return False


def _url_of(obj: object, *, trace_id: str | None = None) -> str | None:
    if obj is None:
        return None
    value = getattr(obj, "get_trace_url", None)
    if callable(value):
        url = None
        if trace_id:
            try:
                url = value(trace_id=trace_id)
            except TypeError:
                url = None
            except Exception:
                url = None
        if not url and not trace_id:
            try:
                url = value()
            except Exception:
                url = None
        if isinstance(url, str) and url:
            return url
    value = getattr(obj, "trace_url", None)
    if isinstance(value, str) and value:
        return value
    return None
