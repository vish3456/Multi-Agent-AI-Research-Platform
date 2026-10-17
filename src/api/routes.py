"""
API routes — ``/research``, ``/status/{job_id}``, ``/health``.

* ``POST /research``  — accepts a query, screens it through the input
  guardrail, enqueues a job on the Redis Stream, and immediately returns
  HTTP 202 with the ``job_id``.

* ``GET /status/{job_id}`` — polls the Redis hash for job status and,
  once completed, returns the full research result.

* ``GET /health`` — lightweight liveness probe for ALB health checks.
"""

from __future__ import annotations

import json
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import require_auth_and_rate_limit
from src.models import (
    JobStatus,
    JobStatusResponse,
    ResearchRequest,
    ResearchResponse,
    ResearchResult,
    EvaluationScores,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# --------------------------------------------------------------------- #
# POST /research
# --------------------------------------------------------------------- #

@router.post(
    "/research",
    response_model=ResearchResponse,
    status_code=202,
    summary="Submit a research query",
    description="Validates auth/rate-limit, screens input through Bedrock "
                "Guardrails, enqueues a job, and returns 202 with the job ID.",
)
async def create_research(
    request: Request,
    body: ResearchRequest,
    _: None = Depends(require_auth_and_rate_limit),
) -> ResearchResponse:
    # 1. Input guardrail check
    guardrails = request.app.state.guardrails
    is_safe, blocked_msg = await guardrails.check(body.query, source="INPUT")
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Input blocked: {blocked_msg}")

    # 2. Generate job ID
    job_id = str(uuid.uuid4())

    # 3. Enqueue to Redis Stream
    producer = request.app.state.producer
    await producer.enqueue(job_id=job_id, query=body.query, session_id=body.session_id)

    # 4. Set initial status
    redis_client = request.app.state.redis
    await redis_client.hset(f"job:{job_id}", mapping={"status": JobStatus.QUEUED.value})
    await redis_client.expire(f"job:{job_id}", 3600)

    logger.info("Job %s enqueued for query: '%s…'", job_id, body.query[:60])
    return ResearchResponse(job_id=job_id, status=JobStatus.QUEUED)


# --------------------------------------------------------------------- #
# GET /status/{job_id}
# --------------------------------------------------------------------- #

@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    summary="Check job status",
    description="Poll for the status and result of a previously submitted job.",
)
async def get_status(
    request: Request,
    job_id: str,
) -> JobStatusResponse:
    redis_client = request.app.state.redis
    data = await redis_client.hgetall(f"job:{job_id}")

    if not data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Decode bytes → str if needed
    decoded = {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
        for k, v in data.items()
    }

    status = decoded.get("status", JobStatus.QUEUED.value)
    error = decoded.get("error")
    result = None

    if status == JobStatus.COMPLETED.value and "result" in decoded:
        raw = json.loads(decoded["result"])
        eval_data = raw.get("evaluation")
        evaluation = None
        if eval_data and isinstance(eval_data, dict):
            evaluation = EvaluationScores(**eval_data)

        result = ResearchResult(
            job_id=raw.get("job_id", job_id),
            query=raw.get("query", ""),
            report=raw.get("report", ""),
            sources=raw.get("sources", []),
            evaluation=evaluation,
            cached=raw.get("cached", False),
        )

    return JobStatusResponse(
        job_id=job_id,
        status=JobStatus(status),
        result=result,
        error=error,
    )


# --------------------------------------------------------------------- #
# GET /health
# --------------------------------------------------------------------- #

@router.get(
    "/health",
    summary="Health check",
    description="Lightweight liveness probe for ALB / container orchestrator.",
)
async def health() -> dict:
    return {"status": "healthy", "service": "multi-agent-research-platform"}
