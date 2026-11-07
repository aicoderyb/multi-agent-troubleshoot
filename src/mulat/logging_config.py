"""Central logging setup for the mulat application."""

from __future__ import annotations

import logging
from logging.config import dictConfig

from mulat.config import settings

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """Configure root and mulat loggers once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = (settings.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": _LOG_FORMAT,
                    "datefmt": _DATE_FORMAT,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "standard",
                },
            },
            "loggers": {
                "mulat": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.access": {"handlers": ["console"], "level": level, "propagate": False},
            },
            "root": {"handlers": ["console"], "level": logging.WARNING},
        }
    )

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger under the mulat namespace.

    Prefer module loggers: get_logger(__name__) → mulat.api.routes.ask
    Names not starting with 'mulat.' are prefixed automatically.
    """
    configure_logging()
    if name.startswith("mulat."):
        return logging.getLogger(name)
    if name == "mulat":
        return logging.getLogger("mulat")
    module = name.removeprefix("src.")
    if module.startswith("mulat."):
        return logging.getLogger(module)
    return logging.getLogger(f"mulat.{module}")
