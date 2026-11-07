"""FastAPI application and lifespan (client initialization)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mulat.api.routes import alert, approve, ask
from mulat.clients.checkpointer import get_checkpointer
from mulat.clients.llm import get_chat_model
from mulat.logging_config import get_logger
from mulat.orchestration.graph import build_graph

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup: initializing checkpointer, LLM, LangGraph")
    checkpointer = get_checkpointer()
    llm = get_chat_model()
    app.state.llm = llm
    app.state.graph = build_graph(checkpointer=checkpointer, llm=llm)
    app.state.checkpointer = checkpointer
    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="mulat",
        description="Kubernetes multi-agent troubleshooter",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(ask.router, tags=["investigation"])
    app.include_router(alert.router, tags=["investigation"])
    app.include_router(approve.router, tags=["approval"])

    return app
