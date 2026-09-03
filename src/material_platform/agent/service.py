from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from material_platform.agent.budgets import AgentBudgets, budgets_for
from material_platform.agent.graph import report_of, run_agent
from material_platform.agent.models import ChatTurn, ResearchReport
from material_platform.agent.retrieve import SelectFn
from material_platform.agent.state import AgentState
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
        checkpointer: object | None = None,
        store: object | None = None,
    ) -> None:
        self._select = select
        self._tracer = tracer or make_tracer()
        self._client = client
        self._budgets = budgets or budgets_for(mode)
        self._checkpointer = checkpointer or MemorySaver()
        self._store = store
        self.last_select_queries: tuple[str, ...] = ()
        self.last_thread_id: str = ""
        self.last_state: AgentState | None = None

    def ask(
        self,
        query: str,
        *,
        thread_id: str | None = None,
        prior_turns: list[ChatTurn] | None = None,
    ) -> ResearchReport:
        state, thread = run_agent(
            query,
            self._select,
            tracer=self._tracer,
            client=self._client,
            budgets=self._budgets,
            checkpointer=self._checkpointer,
            store=self._store,
            thread_id=thread_id,
            prior_turns=prior_turns,
        )
        self.last_select_queries = tuple(item.query for item in state.history)
        self.last_thread_id = thread
        self.last_state = state
        return report_of(state)

    def select(
        self,
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
    ) -> tuple[Citation, ...]:
        return self._select(query, limit=limit, material_type=material_type)
