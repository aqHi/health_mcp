from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .config import get_settings

settings = get_settings()

def _create_engine():
    uri = settings.sqlalchemy_database_uri
    connect_args = {}
    if uri.startswith("sqlite"):  # pragma: no cover - convenience for local dev/tests
        connect_args["check_same_thread"] = False
    return create_engine(uri, pool_pre_ping=True, connect_args=connect_args)


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    with session_scope() as session:
        yield session
