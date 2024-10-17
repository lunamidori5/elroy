import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from rich.console import Console
from sqlalchemy import NullPool, create_engine
from sqlmodel import Session

from elroy.logging_config import setup_logging

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ElroyEnv(Enum):
    TESTING = "testing"
    LOCAL = "local"


@dataclass
class ElroyConfig:
    database_url: str
    openai_api_key: str
    local_storage_path: Optional[str]
    context_window_token_limit: int
    context_refresh_token_trigger_limit: int  # how many tokens we reach before triggering refresh
    context_refresh_token_target: int  # how many tokens we aim to have after refresh
    log_file_path: str


def str_to_bool(input: Optional[str]) -> bool:
    return input is not None and input.lower() in ["true", "1"]


def get_config(
    database_url: str,
    openai_api_key: str,
    local_storage_path: Optional[str] = None,
    context_window_token_limit: Optional[int] = None,
    log_file_path: Optional[str] = None,
) -> ElroyConfig:
    log_file_path = log_file_path or os.path.join(ROOT_DIR, "logs", "elroy.log")
    context_window_token_limit = context_window_token_limit or 16384

    # Set up logging
    setup_logging(log_file_path)

    return ElroyConfig(
        database_url=database_url,
        openai_api_key=openai_api_key,
        local_storage_path=local_storage_path or ".cache",
        context_window_token_limit=context_window_token_limit,
        context_refresh_token_trigger_limit=int(context_window_token_limit * 0.66),
        context_refresh_token_target=int(context_window_token_limit * 0.33),
        log_file_path=log_file_path,
    )


from contextlib import contextmanager
from typing import Generator


@contextmanager
def session_manager(database_url: str) -> Generator[Session, None, None]:
    session = Session(create_engine(database_url, poolclass=NullPool))
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_elroy_env() -> ElroyEnv:
    if os.environ.get("PYTEST_VERSION"):
        return ElroyEnv.TESTING
    else:
        return ElroyEnv.LOCAL


is_test_env = lambda: _get_elroy_env() == ElroyEnv.TESTING


@dataclass
class ElroyContext:
    session: Session
    console: Console
    config: ElroyConfig
    user_id: int
