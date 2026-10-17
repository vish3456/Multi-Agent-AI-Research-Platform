"""
Agent state — shared ``TypedDict`` flowing through every LangGraph node.

Each agent node reads from and writes to this state.  Fields accumulate
as the pipeline progresses: Search → Summarize → Writer → Critic.
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    """
    The pipeline's shared state object.

    Attributes
    ----------
    query : str
        The original user research question.
    session_history : list[dict]
        Previous conversation turns (from Redis session memory).
    related_memories : list[dict]
        Related prior reports from pgvector (similarity 0.50–0.88).
    search_results : list[str]
        Key facts/claims discovered by the Search agent.
    summary_bullets : list[str]
        Condensed bullet points produced by the Summarize agent.
    draft_report : str
        Full structured report drafted by the Writer agent.
    critic_feedback : str
        Textual feedback from the Critic agent (used on retries).
    critic_passed : bool
        Whether the Critic accepted the current draft.
    retry_count : int
        Number of Critic → Search retry loops executed so far.
    final_report : str
        The accepted report (set only when Critic passes).
    sources : list[str]
        Cited sources extracted during the pipeline.
    """

    query: str
    session_history: list[dict]
    related_memories: list[dict]
    search_results: list[str]
    summary_bullets: list[str]
    draft_report: str
    critic_feedback: str
    critic_passed: bool
    retry_count: int
    final_report: str
    sources: list[str]
