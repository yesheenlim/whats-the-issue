from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.manager import AgentManager
from app.api.routes import router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    app.state.settings = settings
    app.state.agent_manager = AgentManager()
    yield
    # Shutdown — nothing to clean up for in-memory


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
