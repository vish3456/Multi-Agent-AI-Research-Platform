"""
LLM-as-judge evaluator — scores every completed research report on four
dimensions (relevance, completeness, hallucination, quality).

Scores are 0–10 floats.  For ``hallucination`` a higher score means
*fewer* hallucinations (10 = fully grounded).

Results are logged to LangSmith via the ``@traceable`` decorator and
stored alongside the report in Redis and PostgreSQL.
"""

from __future__ import annotations

import json
import logging

try:
    from langsmith import traceable
except ImportError:
    # Safe no-op fallback when langsmith is not installed or running in minimal env
    def traceable(name: str | None = None, **kwargs):  # type: ignore
        def decorator(fn):
            return fn
        return decorator

from src.llm.gateway import TensorZeroClient

logger = logging.getLogger(__name__)


@traceable(name="llm_judge")
async def evaluate_report(
    query: str,
    report: str,
    tz_client: TensorZeroClient,
) -> dict:
    """
    Score a research report using an LLM judge.

    Parameters
    ----------
    query : str
        The original research question.
    report : str
        The final report text to evaluate.
    tz_client : TensorZeroClient
        Gateway client for the ``critic`` function.

    Returns
    -------
    dict
        ``{"relevance": float, "completeness": float,
          "hallucination": float, "quality": float}``
        Each score in [0, 10].
    """
    prompt = f"""You are an impartial research-quality judge.  Score the following
research report on a 0–10 scale for each dimension.

Scoring guide:
• **Relevance** — How directly does the report address the query?
• **Completeness** — Does it cover all important aspects of the topic?
• **Hallucination** — 10 = fully grounded, 0 = entirely fabricated.
• **Quality** — Overall writing quality, structure, and clarity.

Research Query:
{query}

Research Report:
{report}

Respond with ONLY a JSON object (no markdown fences):
{{"relevance": <0-10>, "completeness": <0-10>, "hallucination": <0-10>, "quality": <0-10>}}
"""

    try:
        response = await tz_client.inference(
            function_name="critic",
            messages=[{"role": "user", "content": prompt}],
        )

        # Strip possible markdown code fences or conversational text
        cleaned = response.strip()
        if "{" in cleaned and "}" in cleaned:
            cleaned = cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]
        elif cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        scores = json.loads(cleaned)

        # Clamp values to [0, 10]
        for key in ("relevance", "completeness", "hallucination", "quality"):
            val = float(scores.get(key, 5.0))
            scores[key] = max(0.0, min(10.0, val))

        logger.info(
            "Evaluation scores — rel=%.1f comp=%.1f hall=%.1f qual=%.1f",
            scores["relevance"],
            scores["completeness"],
            scores["hallucination"],
            scores["quality"],
        )
        return scores

    except Exception:
        logger.exception("LLM judge evaluation failed; returning defaults.")
        return {
            "relevance": 5.0,
            "completeness": 5.0,
            "hallucination": 5.0,
            "quality": 5.0,
        }
