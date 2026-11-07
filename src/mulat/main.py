"""ASGI entrypoint: `uvicorn mulat.main:app`."""

import uvicorn

from mulat.api.app import create_app
from mulat.config import settings
from mulat.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

app = create_app()
logger.info("mulat ASGI app loaded")


def cli() -> None:
    uvicorn.run(
        "mulat.main:app",
        host=settings.mulat_host,
        port=settings.mulat_port,
        reload=False,
    )


if __name__ == "__main__":
    cli()
