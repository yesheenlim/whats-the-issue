"""AgentManager and LangGraph pipeline wiring."""

import asyncio
import logging
import uuid
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from app.agent.nodes import (
    ClassifyNode,
    FetchNode,
    FormatNode,
    RepoSummaryNode,
    SummarizeNode,
)
from app.agent.schemas import ClassifiedIssue, RawIssue, SummarizedIssue
from app.config import Settings
from app.models import Job, JobStatus

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State passed between LangGraph nodes throughout the triage pipeline."""

    github_url: str
    github_token: str
    top_k_issues: int
    top_n_comments: int
    raw_issues: list[RawIssue]
    classified_issues: list[ClassifiedIssue]
    summarized_issues: list[SummarizedIssue]
    repo_summary: str
    output: dict[str, Any]


class AgentManager:
    """Manages job submission, execution, and result retrieval.

    Wraps a compiled LangGraph pipeline and tracks in-memory job state.
    Each submitted job runs as an asyncio background task.

    Note:
        The internal job store grows unboundedly. This is acceptable for
        development and low-volume use. Production deployments should add
        TTL-based eviction or migrate to Redis.
    """

    def __init__(self, llm: BaseChatModel, settings: Settings) -> None:
        """Initialises AgentManager.

        Args:
            llm: The language model instance shared across all requests.
            settings: Application settings.
        """
        self._settings = settings
        self._memory = MemorySaver()
        self._graph = self._build_graph(llm, settings)
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    def _build_graph(self, llm: BaseChatModel, settings: Settings) -> Any:
        """Compiles the LangGraph pipeline.

        Args:
            llm: The language model instance.
            settings: Application settings.

        Returns:
            A compiled LangGraph runnable.
        """
        provider = settings.LLM_PROVIDER

        builder = StateGraph(AgentState)
        builder.add_node("fetch", FetchNode(settings))
        builder.add_node("classify", ClassifyNode(llm, provider, settings))
        builder.add_node("summarize", SummarizeNode(llm, provider))
        builder.add_node("repo_summary", RepoSummaryNode(llm, provider))
        builder.add_node("format", FormatNode())

        builder.set_entry_point("fetch")
        builder.add_edge("fetch", "classify")
        builder.add_edge("classify", "summarize")
        builder.add_edge("summarize", "repo_summary")
        builder.add_edge("repo_summary", "format")
        builder.add_edge("format", END)

        return builder.compile(checkpointer=self._memory)

    async def submit(
        self,
        github_url: str,
        github_token: str,
        top_k_issues: int,
        top_n_comments: int,
    ) -> str:
        """Submits a new analysis job and returns its thread ID.

        Args:
            github_url: Full URL of the GitHub repository to analyse.
            github_token: GitHub personal access token for API authentication.
            top_k_issues: Maximum number of issues to analyse.
            top_n_comments: Maximum number of recent comments to include per issue.

        Returns:
            A UUID string identifying the job for polling.
        """
        thread_id = str(uuid.uuid4())
        async with self._lock:
            self._jobs[thread_id] = Job(
                thread_id=thread_id, status=JobStatus.PENDING
            )
        asyncio.create_task(
            self._run(thread_id, github_url, github_token, top_k_issues, top_n_comments)
        )
        logger.info("Job %s submitted for %s", thread_id, github_url)
        return thread_id

    async def _run(
        self,
        thread_id: str,
        github_url: str,
        github_token: str,
        top_k_issues: int,
        top_n_comments: int,
    ) -> None:
        """Executes the triage pipeline as a background task.

        Updates job state on start, completion, and failure.

        Args:
            thread_id: The job identifier.
            github_url: Full URL of the GitHub repository.
            github_token: GitHub personal access token.
            top_k_issues: Maximum number of issues to analyse.
            top_n_comments: Maximum number of recent comments per issue.
        """
        async with self._lock:
            self._jobs[thread_id].status = JobStatus.RUNNING

        try:
            config = {"configurable": {"thread_id": thread_id}}
            result = await self._graph.ainvoke(
                {
                    "github_url": github_url,
                    "github_token": github_token,
                    "top_k_issues": top_k_issues,
                    "top_n_comments": top_n_comments,
                    "raw_issues": [],
                    "classified_issues": [],
                    "summarized_issues": [],
                    "repo_summary": "",
                    "output": {},
                },
                config=config,
            )
            async with self._lock:
                self._jobs[thread_id].status = JobStatus.COMPLETE
                self._jobs[thread_id].result = result.get("output", {})
            logger.info("Job %s completed successfully", thread_id)

        except Exception as exc:  # pylint: disable=broad-except
            # Broad catch is intentional: any unhandled error in the pipeline
            # should be captured and surfaced via the polling endpoint.
            logger.exception("Job %s failed: %s", thread_id, exc)
            async with self._lock:
                self._jobs[thread_id].status = JobStatus.FAILED
                self._jobs[thread_id].error = str(exc)

    async def get_job(self, thread_id: str) -> Job | None:
        """Returns the current state of a job by thread ID.

        Args:
            thread_id: The job identifier returned at submission.

        Returns:
            The Job object, or None if no job exists for the given thread ID.
        """
        async with self._lock:
            return self._jobs.get(thread_id)
