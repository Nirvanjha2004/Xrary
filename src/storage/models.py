"""SQLAlchemy ORM models for the hiring agent."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, declarative_base

Base = declarative_base()


class SeenTweet(Base):
    """Model for tracking tweets that have been processed."""
    
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
    """Model for storing hiring agent state and metrics."""
    
    __tablename__ = "agent_state"

    id = Column(Integer, primary_key=True)
    last_run = Column(DateTime, nullable=True)
    notifications_sent = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


__all__ = ["Base", "SeenTweet", "AgentState"]
