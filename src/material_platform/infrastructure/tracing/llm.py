from __future__ import annotations

import json

from material_platform.domain.protocols import LlmClient
from material_platform.infrastructure.tracing.trace import Tracer


class TracedLlmClient:
    def __init__(self, inner: LlmClient, tracer: Tracer, *, name: str = "llm") -> None:
        self.inner = inner
        self._tracer = tracer
        self._name = name

    def complete_json(self, prompt: str) -> dict[str, object]:
        with self._tracer.span("llm", step=self._name):
            self._tracer.set_input(prompt)
            try:
                payload = self.inner.complete_json(prompt)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self._tracer.generation(
                    self._name, prompt, message, step=self._name
                )
                self._tracer.set_output({"error": message})
                raise
            dumped = json.dumps(payload, default=str)
            self._tracer.generation(self._name, prompt, dumped, step=self._name)
            self._tracer.set_output(payload)
            return payload


def named_llm(
    client: LlmClient | None, tracer: Tracer, name: str
) -> LlmClient | None:
    if client is None:
        return None
    inner = client.inner if isinstance(client, TracedLlmClient) else client
    return TracedLlmClient(inner, tracer, name=name)
