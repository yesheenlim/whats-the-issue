from fastapi import APIRouter, Header, HTTPException, Request
from fastapi import status as http_status

from app.models import AnalyzeRequest, AnalyzeResponse, JobStatus, PollResponse

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("", response_model=AnalyzeResponse, status_code=http_status.HTTP_202_ACCEPTED)
async def submit_analysis(
    request: Request,
    body: AnalyzeRequest,
    x_github_token: str = Header(..., description="GitHub personal access token"),
) -> AnalyzeResponse:
    manager = request.app.state.agent_manager
    thread_id = await manager.submit(
        github_url=str(body.github_url),
        github_token=x_github_token,
        top_k=body.top_k,
    )
    return AnalyzeResponse(thread_id=thread_id, status=JobStatus.PENDING)


@router.get("/{thread_id}", response_model=PollResponse)
async def poll_analysis(thread_id: str, request: Request) -> PollResponse:
    manager = request.app.state.agent_manager
    job = await manager.get_job(thread_id)

    if job is None:
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
