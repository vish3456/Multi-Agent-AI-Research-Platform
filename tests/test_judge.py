import asyncio
from unittest.mock import AsyncMock
from src.evaluation.judge import evaluate_report


def test_judge_parses_clean_json():
    async def _run():
        mock_tz = AsyncMock()
        mock_tz.inference.return_value = '{"relevance": 9.2, "completeness": 8.5, "hallucination": 9.9, "quality": 8.8}'

        scores = await evaluate_report("query", "report", mock_tz)
        assert scores["relevance"] == 9.2
        assert scores["completeness"] == 8.5
        assert scores["hallucination"] == 9.9
        assert scores["quality"] == 8.8

    asyncio.run(_run())


def test_judge_parses_markdown_and_preamble():
    async def _run():
        mock_tz = AsyncMock()
        mock_tz.inference.return_value = """Here is my assessment of the report:
```json
{
  "relevance": 12.0,
  "completeness": -2.0,
  "hallucination": 7.5,
  "quality": 8.0
}
```
Hope this helps!"""

        scores = await evaluate_report("query", "report", mock_tz)
        # Check clamping to [0, 10]
        assert scores["relevance"] == 10.0
        assert scores["completeness"] == 0.0
        assert scores["hallucination"] == 7.5
        assert scores["quality"] == 8.0

    asyncio.run(_run())


def test_judge_fallback_on_invalid_output():
    async def _run():
        mock_tz = AsyncMock()
        mock_tz.inference.return_value = "Sorry, I cannot evaluate this report."

        scores = await evaluate_report("query", "report", mock_tz)
        assert scores == {
            "relevance": 5.0,
            "completeness": 5.0,
            "hallucination": 5.0,
            "quality": 5.0,
        }

    asyncio.run(_run())
