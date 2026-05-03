"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, HttpUrl


class JobStatus(str):
    """String constants for job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class Job(BaseModel):
    """Internal job state tracked by AgentManager."""

    thread_id: str
    status: str
    result: dict | None = None
    error: str | None = None


class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze."""

    github_url: HttpUrl
    top_k_issues: int = 50
    top_n_comments: int = 5


class AnalyzeResponse(BaseModel):
    """Immediate response returned on job submission."""

    thread_id: str
    status: str


class PollResponse(BaseModel):
    """Response returned when polling a job by thread ID."""

    thread_id: str
    status: str
    result: dict | None = None
    error: str | None = None
