"""
Search agent — Node 1 of the LangGraph pipeline.

Given the user's query and session history, identifies 5–8 key facts,
claims, or data points that need to be researched.  All model calls go
through the TensorZero sidecar.
"""

from __future__ import annotations

import json
import logging

from langsmith import traceable

from src.agents.state import AgentState
from src.llm.gateway import TensorZeroClient

logger = logging.getLogger(__name__)

# Module-level reference injected at startup by the worker.
_tz_client: TensorZeroClient | None = None


def set_tz_client(client: TensorZeroClient) -> None:
    """Inject the TensorZero client (called once during app startup)."""
    global _tz_client
    _tz_client = client


@traceable(name="search_agent")
async def search_node(state: AgentState) -> dict:
    """
    Analyse the query and session context to extract key research points.

    Writes ``search_results`` (list of fact strings) into the state.
    """
    assert _tz_client is not None, "TensorZero client not initialised"

    history_snippet = ""
    if state.get("session_history"):
        recent = state["session_history"][-5:]
        history_snippet = "\n".join(
            f"  {entry.get('role', '?')}: {entry.get('content', '')}" for entry in recent
        )

    critic_context = ""
    if state.get("critic_feedback"):
        critic_context = (
            f"\n\nPrevious Attempt Feedback (retry #{state['retry_count']}):\n"
            f"{state['critic_feedback']}\n"
            "Improve your research to address the above feedback."
        )

    prompt = f"""You are a meticulous research analyst. Given the research query below,
identify 5–8 specific key facts, statistics, claims, or data points that
should be investigated to produce a comprehensive research report.

Return your findings as a JSON array of strings, e.g.:
["fact 1", "fact 2", ...]

Research Query: {state['query']}

{'Session Context:' + chr(10) + history_snippet if history_snippet else ''}
{critic_context}
"""

    response = await _tz_client.inference(
        function_name="search",
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse the JSON array; fall back to splitting on newlines
    try:
        facts = json.loads(response)
        if not isinstance(facts, list):
            facts = [str(facts)]
    except (json.JSONDecodeError, TypeError):
        facts = [line.strip("- •").strip() for line in response.split("\n") if line.strip()]

    logger.info("Search agent found %d facts.", len(facts))
    return {"search_results": facts}
