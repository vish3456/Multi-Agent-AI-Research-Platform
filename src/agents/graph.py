"""
LangGraph pipeline — wires the four agent nodes into a ``StateGraph`` with
a conditional Critic → Search retry edge.

    START → Search → Summarize → Writer → Critic
                                            │
                                ┌───fail────┘
                                ▼
                             Search (retry)
                             (max 3 retries)

The compiled graph is returned by ``build_research_graph()`` and invoked
by the background worker with ``graph.ainvoke(initial_state)``.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from src.agents.state import AgentState
from src.agents.search_agent import search_node
from src.agents.summarize_agent import summarize_node
from src.agents.writer_agent import writer_node
from src.agents.critic_agent import critic_node

logger = logging.getLogger(__name__)


def _should_retry(state: AgentState) -> str:
    """
    Conditional edge function for the Critic node.

    Returns ``"retry"`` if the Critic failed the report **and** the retry
    budget has not been exhausted.  Otherwise returns ``"accept"``.
    """
    if not state["critic_passed"] and state["retry_count"] < 3:
        logger.info("Critic FAILED — routing back to Search (retry #%d).", state["retry_count"])
        return "retry"
    return "accept"


should_retry = _should_retry


def build_research_graph() -> StateGraph:
    """
    Build and compile the four-agent research pipeline.

    Returns
    -------
    CompiledGraph
        A compiled LangGraph ``StateGraph`` ready for ``ainvoke``.
    """
    workflow = StateGraph(AgentState)

    # --- Nodes ---
    workflow.add_node("search", search_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("critic", critic_node)

    # --- Edges ---
    workflow.add_edge(START, "search")
    workflow.add_edge("search", "summarize")
    workflow.add_edge("summarize", "writer")
    workflow.add_edge("writer", "critic")

    # Critic → conditional: retry from Search or accept → END
    workflow.add_conditional_edges(
        "critic",
        _should_retry,
        {
            "retry": "search",
            "accept": END,
        },
    )

    compiled = workflow.compile()
    logger.info("LangGraph research pipeline compiled successfully.")
    return compiled
