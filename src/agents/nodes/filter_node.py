"""Filter node for cheap keyword filtering and deduplication."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.clients.x_reverse_client import Tweet
from src.services.deduplicator import Deduplicator
from src.services.tweet_filter import cheap_filter

if TYPE_CHECKING:
	from src.agents.hiring_agent import AgentState

logger = structlog.get_logger()


def filter_node(state: AgentState, deduplicator: Deduplicator) -> dict[str, list[Tweet] | int]:
	"""Filter tweets with cheap rules and drop previously seen items."""
	node_logger = logger.bind(node="filter")
	filtered_tweets: list[Tweet] = []
	error_count = state.get("error_count", 0)

	try:
		tweets = state.get("tweets", [])
		node_logger.info("filter node start", tweet_count=len(tweets))

		for tweet in tweets:
			try:
				if not cheap_filter(tweet):
					continue
				if deduplicator.is_seen(tweet.id):
					continue
				filtered_tweets.append(tweet)
			except Exception as exc:
				error_count += 1
				node_logger.error(
					"filter decision failed",
					tweet_id=getattr(tweet, "id", None),
					error=str(exc),
					error_type=type(exc).__name__,
				)

		node_logger.info("filter node complete", filtered_count=len(filtered_tweets))
		return {
			"filtered_tweets": filtered_tweets,
			"error_count": error_count,
		}
	except Exception as exc:
		node_logger.error(
			"filter node failed",
			error=str(exc),
			error_type=type(exc).__name__,
		)
		return {
			"filtered_tweets": [],
			"error_count": error_count + 1,
		}


__all__ = ["filter_node"]
