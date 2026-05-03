import asyncio
import uuid
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from app.agent.nodes import (
    make_classify_node,
    make_fetch_node,
    make_format_node,
    make_repo_summary_node,
    make_summarize_node,
)
from app.config import Settings
from app.models import Job, JobStatus


class AgentState(TypedDict):
    github_url: str
    github_token: str
    top_k: int
    raw_issues: list[dict]
    classified_issues: list[dict]
    summarized_issues: list[dict]
    repo_summary: str
    output: dict


class AgentManager:
    def __init__(self, llm: BaseChatModel, settings: Settings) -> None:
        self._memory = MemorySaver()
        self._graph = self._build_graph(llm, settings)
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    def _build_graph(self, llm: BaseChatModel, settings: Settings):
        provider = settings.LLM_PROVIDER

        builder = StateGraph(AgentState)
        builder.add_node("fetch", make_fetch_node(settings))
        builder.add_node("classify", make_classify_node(llm, provider, settings))
        builder.add_node("summarize", make_summarize_node(llm, provider))
        builder.add_node("repo_summary", make_repo_summary_node(llm, provider))
        builder.add_node("format", make_format_node())

        builder.set_entry_point("fetch")
        builder.add_edge("fetch", "classify")
        builder.add_edge("classify", "summarize")
        builder.add_edge("summarize", "repo_summary")
        builder.add_edge("repo_summary", "format")
        builder.add_edge("format", END)

        return builder.compile(checkpointer=self._memory)

    async def submit(self, github_url: str, github_token: str, top_k: int) -> str:
        thread_id = str(uuid.uuid4())
        async with self._lock:
            self._jobs[thread_id] = Job(thread_id=thread_id, status=JobStatus.PENDING)
        asyncio.create_task(self._run(thread_id, github_url, github_token, top_k))
        return thread_id

    async def _run(self, thread_id: str, github_url: str, github_token: str, top_k: int) -> None:
        async with self._lock:
            self._jobs[thread_id].status = JobStatus.RUNNING

        try:
            config = {"configurable": {"thread_id": thread_id}}
            result = await self._graph.ainvoke(
                {
                    "github_url": github_url,
                    "github_token": github_token,
                    "top_k": top_k,
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

        except Exception as exc:
            async with self._lock:
                self._jobs[thread_id].status = JobStatus.FAILED
                self._jobs[thread_id].error = str(exc)

    async def get_job(self, thread_id: str) -> Optional[Job]:
        async with self._lock:
            return self._jobs.get(thread_id)
