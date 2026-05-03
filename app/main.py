from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.llm_factory import create_llm
from app.agent.manager import AgentManager
from app.api.routes import router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    llm = create_llm(settings)
    app.state.settings = settings
    app.state.agent_manager = AgentManager(llm=llm, settings=settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="gh-triage",
        description="Async GitHub issue analysis API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
