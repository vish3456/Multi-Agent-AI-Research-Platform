"""
Critic agent — Node 4 of the LangGraph pipeline.

Fact-checks the Writer's draft against the original search results,
evaluating accuracy, completeness, coherence, and source citation.
Decides pass / fail; on failure the pipeline retries from Search.
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


@traceable(name="critic_agent")
async def critic_node(state: AgentState) -> dict:
    """
    Evaluate the draft report for quality.

    Writes ``critic_passed``, ``critic_feedback``, ``final_report``,
    ``sources``, and an incremented ``retry_count`` into the state.
    """
    assert _tz_client is not None, "TensorZero client not initialised"

    search_text = "\n".join(f"- {r}" for r in state["search_results"])

    prompt = f"""You are a rigorous research quality critic. Evaluate the following
research report against the original search results.

Evaluate on four dimensions:
1. **Factual accuracy** — does the report faithfully represent the search results?
2. **Completeness** — does it cover all key points from the search results?
3. **Logical coherence** — is the report well-structured and internally consistent?
4. **Source citation** — does it reference or attribute findings appropriately?

Research Query: {state['query']}

Original Search Results:
{search_text}

Draft Report:
{state['draft_report']}

Respond with a JSON object exactly like this:
{{
    "passed": true or false,
    "feedback": "Detailed feedback explaining your assessment...",
    "sources": ["source 1", "source 2"]
}}

Set "passed" to true only if the report is factually accurate, complete,
coherent, and properly sourced.  Otherwise set it to false and provide
specific, actionable feedback.
"""

    response = await _tz_client.inference(
        function_name="critic",
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse the structured response
    try:
        result = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        # If the model doesn't return valid JSON, treat as a pass to
        # avoid blocking the pipeline on a format issue
        logger.warning("Critic returned non-JSON; treating as PASS.")
        result = {"passed": True, "feedback": response, "sources": []}

    passed = bool(result.get("passed", True))
    feedback = result.get("feedback", "")
    sources = result.get("sources", [])

    new_retry = state["retry_count"] + (0 if passed else 1)

    # If retries are exhausted, force acceptance
    if not passed and new_retry >= 3:
        logger.warning("Critic FAILED but retry limit (3) reached — accepting report.")
        passed = True
        feedback += " [Accepted after max retries.]"

    logger.info(
        "Critic verdict: %s (retry_count=%d)", "PASS" if passed else "FAIL", new_retry
    )

    return {
        "critic_passed": passed,
        "critic_feedback": feedback,
        "final_report": state["draft_report"] if passed else "",
        "sources": sources,
        "retry_count": new_retry,
    }
