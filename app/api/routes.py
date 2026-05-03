"""FastAPI route definitions for the /analyze endpoint."""

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi import status as http_status

from app.models import AnalyzeRequest, AnalyzeResponse, JobStatus, PollResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post(
    "",
    response_model=AnalyzeResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def submit_analysis(
    request: Request,
    body: AnalyzeRequest,
    x_github_token: str = Header(..., description="GitHub personal access token"),
) -> AnalyzeResponse:
    """Submits a GitHub repository for issue triage analysis.

    Args:
        request: The incoming FastAPI request (used to access app state).
        body: The request body containing the GitHub URL and analysis options.
        x_github_token: GitHub personal access token passed as a request header.

    Returns:
        An AnalyzeResponse containing the thread ID and initial job status.
    """
    manager = request.app.state.agent_manager
    thread_id = await manager.submit(
        github_url=str(body.github_url),
        github_token=x_github_token,
        top_k_issues=body.top_k_issues,
        top_n_comments=body.top_n_comments,
    )
    return AnalyzeResponse(thread_id=thread_id, status=JobStatus.PENDING)


@router.get("/{thread_id}", response_model=PollResponse)
async def poll_analysis(thread_id: str, request: Request) -> PollResponse:
    """Returns the current status and result of a submitted analysis job.

    Args:
        thread_id: The job identifier returned by the submit endpoint.
        request: The incoming FastAPI request (used to access app state).

    Returns:
        A PollResponse with job status, result, and error if applicable.

    Raises:
        HTTPException: 404 if no job exists for the given thread ID.
    """
    manager = request.app.state.agent_manager
    job = await manager.get_job(thread_id)

    if job is None:
        logger.warning("Poll request for unknown thread_id: %s", thread_id)
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )

    return PollResponse(
        thread_id=job.thread_id,
        status=job.status,
        result=job.result,
        error=job.error,
    )
