from __future__ import annotations

from material_platform.agent.budgets import AgentBudgets, budgets_for
from material_platform.agent.graph import report_of, run_agent
from material_platform.agent.models import ResearchReport
from material_platform.agent.retrieve import SelectFn
from material_platform.agent.trace import Tracer, make_tracer
from material_platform.analysis.protocol import LlmClient
from material_platform.domain.citation import Citation


class ResearchAgent:
    def __init__(
        self,
        select: SelectFn,
        *,
        tracer: Tracer | None = None,
        client: LlmClient | None = None,
        mode: str = "standard",
        budgets: AgentBudgets | None = None,
    ) -> None:
        self._select = select
        self._tracer = tracer or make_tracer()
        self._client = client
        self._budgets = budgets or budgets_for(mode)
        self.last_select_queries: tuple[str, ...] = ()

    def ask(self, query: str) -> ResearchReport:
        state = run_agent(
            query,
            self._select,
            tracer=self._tracer,
            client=self._client,
            budgets=self._budgets,
        )
        self.last_select_queries = tuple(item.query for item in state.history)
        return report_of(state)

    def select(
        self,
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
    ) -> tuple[Citation, ...]:
        _ = material_type
        report = self.ask(query)
        return report.citations[:limit]
