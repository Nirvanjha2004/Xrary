"""Judge node for LLM-based hiring classification."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Coroutine, TypeVar

import structlog

from src.clients.llm_client import JudgeResult, LLMClient
from src.clients.x_reverse_client import Tweet

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


def judge_node(
	state: AgentState,
	llm_client: LLMClient,
) -> dict[str, list[tuple[Tweet, JudgeResult]] | int]:
	"""Judge filtered tweets and keep only high-confidence hiring posts."""
	node_logger = logger.bind(node="judge")
	judged_tweets: list[tuple[Tweet, JudgeResult]] = []
	error_count = state.get("error_count", 0)

	try:
		filtered_tweets = state.get("filtered_tweets", [])
		node_logger.info("judge node start", tweet_count=len(filtered_tweets))

		for tweet in filtered_tweets:
			try:
				result = _run_async(llm_client.judge_tweet(tweet.text, tweet.author_handle))
				if result.is_hiring and result.confidence > 0.7:
					judged_tweets.append((tweet, result))
			except Exception as exc:
				error_count += 1
				node_logger.error(
					"judge decision failed",
					tweet_id=getattr(tweet, "id", None),
					error=str(exc),
					error_type=type(exc).__name__,
				)

		node_logger.info("judge node complete", judged_count=len(judged_tweets))
		return {
			"judged_tweets": judged_tweets,
			"error_count": error_count,
		}
	except Exception as exc:
		node_logger.error(
			"judge node failed",
			error=str(exc),
			error_type=type(exc).__name__,
		)
		return {
			"judged_tweets": [],
			"error_count": error_count + 1,
		}


__all__ = ["judge_node"]
