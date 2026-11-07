"""Checkpointer: MemorySaver locally, Postgres when DATABASE_URL is set."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from mulat.config import settings
from mulat.logging_config import get_logger

logger = get_logger(__name__)


def get_checkpointer() -> BaseCheckpointSaver:
    if settings.database_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise RuntimeError(
                "Install mulat[postgres] and set DATABASE_URL for Postgres checkpointer"
            ) from exc
        logger.info("Checkpointer: Postgres")
        return PostgresSaver.from_conn_string(settings.database_url)
    logger.info("Checkpointer: MemorySaver")
    return MemorySaver()
