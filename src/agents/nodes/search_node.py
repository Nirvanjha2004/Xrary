"""Search node for fetching tweets from X."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Coroutine, TypeVar

import structlog

from src.clients.x_reverse_client import Tweet, XReverseClient

if TYPE_CHECKING:
	from src.agents.hiring_agent import AgentState

logger = structlog.get_logger()
T = TypeVar("T")


def _run_async(coroutine: Coroutine[Any, Any, T]) -> T:
	"""Run an async coroutine from synchronous node code."""
	try:
		asyncio.get_running_loop()
	except RuntimeError:
		return asyncio.run(coroutine)

	loop = asyncio.new_event_loop()
	try:
		return loop.run_until_complete(coroutine)
	finally:
		loop.close()


def search_node(state: AgentState, x_client: XReverseClient) -> dict[str, list[Tweet] | int]:
	"""Fetch tweets and return a state patch for downstream nodes."""
	node_logger = logger.bind(node="search")
	try:
		query = x_client.settings.x_search_query
		node_logger.info("search node start", query=query)
		tweets = _run_async(x_client.search_tweets(query))
		node_logger.info("search node complete", tweet_count=len(tweets))
		return {"tweets": tweets}
	except Exception as exc:
		node_logger.error(
			"search node failed",
			error=str(exc),
			error_type=type(exc).__name__,
		)
		return {
			"tweets": [],
			"error_count": state.get("error_count", 0) + 1,
		}


__all__ = ["search_node"]
