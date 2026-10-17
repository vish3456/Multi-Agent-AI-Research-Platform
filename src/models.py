"""
Pydantic models — request / response schemas and internal data structures.
"""

from __future__ import annotations

import json
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class JobStatus(str, Enum):
    """Lifecycle states for an async research job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    """Inbound payload for POST /research."""

    query: str = Field(..., min_length=1, max_length=4096, description="The research question or topic.")
    session_id: str | None = Field(default=None, description="Optional session ID for conversational context.")


class ResearchResponse(BaseModel):
    """Immediate 202 acknowledgement with the assigned job ID."""

    job_id: str
    status: JobStatus = JobStatus.QUEUED


class JobStatusResponse(BaseModel):
    """Response for GET /status/{job_id}."""

    job_id: str
    status: JobStatus
    result: ResearchResult | None = None
    error: str | None = None


class ResearchResult(BaseModel):
    """The final deliverable returned once the pipeline completes."""

    job_id: str
    query: str
    report: str
    sources: list[str] = Field(default_factory=list)
    evaluation: EvaluationScores | None = None
    cached: bool = False


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class EvaluationScores(BaseModel):
    """Four-dimensional quality scores assigned by the LLM-as-judge."""

    relevance: float = Field(..., ge=0.0, le=10.0)
    completeness: float = Field(..., ge=0.0, le=10.0)
    hallucination: float = Field(..., ge=0.0, le=10.0, description="10 = no hallucination")
    quality: float = Field(..., ge=0.0, le=10.0)


# ---------------------------------------------------------------------------
# Rebuild forward refs (ResearchResult ↔ EvaluationScores)
# ---------------------------------------------------------------------------

JobStatusResponse.model_rebuild()
ResearchResult.model_rebuild()
