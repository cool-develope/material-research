from __future__ import annotations

import json

from material_platform.agent.trace import Tracer
from material_platform.analysis.protocol import LlmClient


class TracedLlmClient:
    def __init__(self, inner: LlmClient, tracer: Tracer, *, name: str = "llm") -> None:
        self.inner = inner
        self._tracer = tracer
        self._name = name

    def complete_json(self, prompt: str) -> dict[str, object]:
        with self._tracer.span("llm", step=self._name):
            payload = self.inner.complete_json(prompt)
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
