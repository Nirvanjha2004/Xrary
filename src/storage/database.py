from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import Settings
from src.storage.models import AgentState, Base, SeenTweet


DATABASE_PATH = Path(Settings.sqlite_db_path)
ENGINE = create_engine(
    f"sqlite:///{DATABASE_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=ENGINE)


def get_db() -> Generator[Session, None, None]:
    with Session(ENGINE) as session:
        yield session


def get_or_create_agent_state(session: Session) -> AgentState:
    statement = select(AgentState).order_by(AgentState.id.asc()).limit(1)
    agent_state = session.scalars(statement).first()
    if agent_state is not None:
        return agent_state

    agent_state = AgentState()
    session.add(agent_state)
    session.flush()
    return agent_state