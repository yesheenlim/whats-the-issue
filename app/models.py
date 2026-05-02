from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, HttpUrl


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class Job(BaseModel):
    thread_id: str
    status: JobStatus
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


# --- Request / Response models ---


class AnalyzeRequest(BaseModel):
    github_url: HttpUrl


class AnalyzeResponse(BaseModel):
    thread_id: str
    status: JobStatus


class PollResponse(BaseModel):
    thread_id: str
    status: JobStatus
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
