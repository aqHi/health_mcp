"""Utility helpers for initializing the database schema."""

import logging
import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .db import engine
from .models import Base

logger = logging.getLogger(__name__)


def wait_for_database(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    """Poll the configured database until a simple query succeeds."""
    attempt = 0
    while True:
        attempt += 1
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Database connection established on attempt %s", attempt)
            return
        except OperationalError as exc:  # pragma: no cover - depends on external service
            if attempt >= max_attempts:
                logger.error("Database not ready after %s attempts", attempt)
                raise
            logger.warning("Database not ready (attempt %s/%s): %s", attempt, max_attempts, exc)
            time.sleep(delay_seconds)


def init_database_schema() -> None:
    """Create all database tables defined in the SQLAlchemy metadata."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema ensured via create_all")


def initialize_database(*, attempts: Optional[int] = None, delay: Optional[float] = None) -> None:
    """Public entrypoint that waits for the database and creates tables."""
    wait_for_database(max_attempts=attempts or 30, delay_seconds=delay or 2.0)
    init_database_schema()


if __name__ == "__main__":  # pragma: no cover - CLI utility
    initialize_database()
