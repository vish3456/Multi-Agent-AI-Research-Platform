"""
Writer agent — Node 3 of the LangGraph pipeline.

Drafts a comprehensive, structured research report from the summarised
bullet points, incorporating any related prior research from long-term
memory and addressing Critic feedback on retries.
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


def _format_memories(memories: list[dict]) -> str:
    """Format related LTM entries into a readable context block."""
    parts: list[str] = []
    for i, mem in enumerate(memories, 1):
        report = mem.get("report", {})
        report_text = report.get("report", str(report)) if isinstance(report, dict) else str(report)
        parts.append(
            f"--- Related Research #{i} (similarity={mem.get('similarity', 0):.2f}) ---\n"
            f"Query: {mem.get('query', 'N/A')}\n"
            f"Report excerpt: {report_text[:500]}…"
        )
    return "\n\n".join(parts)


@traceable(name="writer_agent")
async def writer_node(state: AgentState) -> dict:
    """
    Draft a full structured research report.

    Writes ``draft_report`` into the state.
    """
    assert _tz_client is not None, "TensorZero client not initialised"

    bullets_text = "\n".join(f"• {b}" for b in state["summary_bullets"])

    context_block = ""
    if state.get("related_memories"):
        context_block = (
            "\n\nRelated Prior Research (use as background context, cite if relevant):\n"
            + _format_memories(state["related_memories"])
        )

    critic_block = ""
    if state.get("critic_feedback"):
        critic_block = (
            f"\n\nCritic Feedback from Previous Attempt (retry #{state['retry_count']}):\n"
            f"{state['critic_feedback']}\n"
            "Address all feedback in this revision."
        )

    prompt = f"""You are an expert research writer. Produce a comprehensive, well-structured
research report based on the key points below.

The report MUST include:
1. An executive summary (2–3 sentences)
2. Detailed sections with headers for each major topic
3. Specific data, statistics, and evidence where available
4. A conclusion with key takeaways
5. A list of cited sources (if any)

Research Query: {state['query']}

Key Points:
{bullets_text}
{context_block}
{critic_block}

Write the report in clear, professional prose. Use markdown formatting.
"""

    response = await _tz_client.inference(
        function_name="writer",
        messages=[{"role": "user", "content": prompt}],
    )

    logger.info("Writer agent drafted report (%d chars).", len(response))
    return {"draft_report": response}
