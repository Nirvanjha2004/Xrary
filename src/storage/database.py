from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import Session, declarative_base

from src.config import Settings


Base = declarative_base()
DATABASE_PATH = Path(Settings.sqlite_db_path)
ENGINE = create_engine(
    f"sqlite:///{DATABASE_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)


class SeenTweet(Base):
    __tablename__ = "seen_tweets"

    id = Column(Integer, primary_key=True)
    tweet_id = Column(String(50), unique=True, nullable=False, index=True)
    tweet_text = Column(Text, nullable=False)
    author_handle = Column(String(50), nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)
    confidence_score = Column(Float, nullable=True)
    company = Column(String(200), nullable=True)
    role = Column(String(200), nullable=True)


class AgentState(Base):
    __tablename__ = "agent_state"

    id = Column(Integer, primary_key=True)
    last_run = Column(DateTime, nullable=True)
    notifications_sent = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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