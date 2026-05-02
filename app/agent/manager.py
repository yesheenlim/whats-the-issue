import asyncio
import uuid
from typing import Annotated, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage

from app.models import Job, JobStatus


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    github_url: str
    github_token: str


class AgentManager:
    def __init__(self) -> None:
        self._memory = MemorySaver()
        self._graph = self._build_graph()
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    def _build_graph(self) -> StateGraph:
        """
        Dummy graph that echoes the github_url back.
        Replace the echo_node implementation when the real agent is ready.
        """

        def echo_node(state: AgentState) -> dict:
            echo_message = AIMessage(
                content=f"[DUMMY AGENT] Received request to analyze: {state['github_url']}"
            )
            return {"messages": [echo_message]}

        builder = StateGraph(AgentState)
        builder.add_node("echo", echo_node)
        builder.set_entry_point("echo")
        builder.add_edge("echo", END)
        return builder.compile(checkpointer=self._memory)

    async def submit(self, github_url: str, github_token: str) -> str:
        thread_id = str(uuid.uuid4())

        async with self._lock:
            self._jobs[thread_id] = Job(thread_id=thread_id, status=JobStatus.PENDING)

        asyncio.create_task(self._run(thread_id, github_url, github_token))
        return thread_id

    async def _run(self, thread_id: str, github_url: str, github_token: str) -> None:
        async with self._lock:
            self._jobs[thread_id].status = JobStatus.RUNNING

        try:
            config = {"configurable": {"thread_id": thread_id}}
            result = await self._graph.ainvoke(
                {
                    "messages": [],
                    "github_url": github_url,
                    "github_token": github_token,
                },
                config=config,
            )

            serialized = {
                "messages": [
                    {"type": m.type, "content": m.content}
                    for m in result.get("messages", [])
                ]
            }

            async with self._lock:
                self._jobs[thread_id].status = JobStatus.COMPLETE
                self._jobs[thread_id].result = serialized

        except Exception as exc:
            async with self._lock:
                self._jobs[thread_id].status = JobStatus.FAILED
                self._jobs[thread_id].error = str(exc)

    async def get_job(self, thread_id: str) -> Optional[Job]:
        async with self._lock:
            return self._jobs.get(thread_id)
        