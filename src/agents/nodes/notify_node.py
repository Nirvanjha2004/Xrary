"""Notify node for sending WhatsApp alerts and persisting seen tweets."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.clients.whatsapp_client import WhatsAppClient
from src.services.deduplicator import Deduplicator
from src.services.message_formatter import format_hiring_alert

if TYPE_CHECKING:
	from src.agents.hiring_agent import AgentState

logger = structlog.get_logger()


def notify_node(
	state: AgentState,
	whatsapp_client: WhatsAppClient,
	deduplicator: Deduplicator,
) -> dict[str, int]:
	"""Send notifications for judged tweets and update deduplication state."""
	node_logger = logger.bind(node="notify")
	notifications_sent = state.get("notifications_sent", 0)
	error_count = state.get("error_count", 0)

	try:
		judged_tweets = state.get("judged_tweets", [])
		node_logger.info("notify node start", judged_count=len(judged_tweets))

		for tweet, judge in judged_tweets:
			try:
				message = format_hiring_alert(tweet, judge)
				whatsapp_client.send_notification(message)
				deduplicator.mark_seen(tweet=tweet, judge=judge, notified=True)
				notifications_sent += 1
			except Exception as exc:
				error_count += 1
				node_logger.error(
					"notification failed",
					tweet_id=getattr(tweet, "id", None),
					error=str(exc),
					error_type=type(exc).__name__,
				)

		node_logger.info("notify node complete", notifications_sent=notifications_sent)
		return {
			"notifications_sent": notifications_sent,
			"error_count": error_count,
		}
	except Exception as exc:
		node_logger.error(
			"notify node failed",
			error=str(exc),
			error_type=type(exc).__name__,
		)
		return {
			"notifications_sent": notifications_sent,
			"error_count": error_count + 1,
		}


__all__ = ["notify_node"]
