"""LLM client factory."""

from langchain_openai import ChatOpenAI

from mulat.config import settings
from mulat.logging_config import get_logger

logger = get_logger(__name__)


def get_chat_model() -> ChatOpenAI:
    kwargs: dict = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key or "ollama",
    }
    if settings.openai_api_base:
        kwargs["base_url"] = settings.openai_api_base.rstrip("/")
    logger.info(
        "LLM client model=%s base_url=%s",
        settings.llm_model,
        kwargs.get("base_url", "https://api.openai.com/v1"),
    )
    return ChatOpenAI(**kwargs)
