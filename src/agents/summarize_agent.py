"""
Summarize agent — Node 2 of the LangGraph pipeline.

Condenses the raw search results into structured, concise bullet points
that the Writer agent can expand into a full report.
"""

from __future__ import annotations

import json
import logging

from langsmith import traceable

from src.agents.state import AgentState
from src.llm.gateway import TensorZeroClient

logger = logging.getLogger(__name__)

_tz_client: TensorZeroClient | None = None


def set_tz_client(client: TensorZeroClient) -> None:
    global _tz_client
    _tz_client = client


@traceable(name="summarize_agent")
async def summarize_node(state: AgentState) -> dict:
    """
    Transform raw search findings into structured bullet points.

    Writes ``summary_bullets`` (list of strings) into the state.
    """
    assert _tz_client is not None, "TensorZero client not initialised"

    facts_text = "\n".join(f"- {fact}" for fact in state["search_results"])

    prompt = f"""You are a research summariser. Condense the following raw findings
into clear, structured bullet points. Group related items together and
remove redundancies.

Return your output as a JSON array of strings, e.g.:
["bullet 1", "bullet 2", ...]

Raw Findings:
{facts_text}
"""

    response = await _tz_client.inference(
        function_name="summarize",
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        bullets = json.loads(response)
        if not isinstance(bullets, list):
            bullets = [str(bullets)]
    except (json.JSONDecodeError, TypeError):
        bullets = [line.strip("- •").strip() for line in response.split("\n") if line.strip()]

    logger.info("Summarize agent produced %d bullets.", len(bullets))
    return {"summary_bullets": bullets}
