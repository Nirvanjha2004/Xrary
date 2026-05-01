import datetime

import structlog
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Annotated, TypedDict

from src.clients.llm_client import JudgeResult, LLMClient
from src.clients.whatsapp_client import WhatsAppClient
from src.clients.x_reverse_client import Tweet, XReverseClient
from src.config import Settings
from src.services.deduplicator import Deduplicator
from src.services.message_formatter import format_hiring_alert
from src.services.tweet_filter import cheap_filter
from src.storage.database import get_db, init_db


def _replace_value(_current, updated):
    return updated


class AgentState(TypedDict, total=False):
    tweets: Annotated[list[Tweet], _replace_value]
    filtered_tweets: Annotated[list[Tweet], _replace_value]
    judged_tweets: Annotated[list[tuple[Tweet, JudgeResult]], _replace_value]
    notifications_sent: int
    error_count: int
    last_run: str | None


class HiringAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = structlog.get_logger().bind(component="hiring_agent")
        init_db()
        self.x_client = XReverseClient(settings)
        self.whatsapp_client = WhatsAppClient(settings)
        self.llm_client = LLMClient(settings)
        self.deduplicator = Deduplicator(get_db)
        self.graph = self.compile_graph()

    def _run_async(self, coroutine):
        return __import__("asyncio").run(coroutine)

    def _search_node(self, state: AgentState) -> dict:
        node_logger = self.logger.bind(node="search")
        try:
            node_logger.info("search node start", query=self.settings.x_search_query)
            tweets = self._run_async(self.x_client.search_tweets(self.settings.x_search_query))
            node_logger.info("search node complete", tweet_count=len(tweets))
            return {"tweets": tweets}
        except Exception as exc:
            node_logger.error("search node failed", error=str(exc), error_type=type(exc).__name__)
            return {"tweets": [], "error_count": state.get("error_count", 0) + 1}

    def _filter_node(self, state: AgentState) -> dict:
        node_logger = self.logger.bind(node="filter")
        filtered_tweets = []
        error_count = state.get("error_count", 0)

        try:
            tweets = state.get("tweets", [])
            node_logger.info("filter node start", tweet_count=len(tweets))
            for tweet in tweets:
                try:
                    if not cheap_filter(tweet):
                        node_logger.debug("tweet rejected by cheap filter", tweet_id=tweet.id)
                        continue

                    if self.deduplicator.is_seen(tweet.id):
                        node_logger.debug("tweet already seen", tweet_id=tweet.id)
                        continue

                    filtered_tweets.append(tweet)
                    node_logger.debug("tweet passed filter", tweet_id=tweet.id)
                except Exception as exc:
                    error_count += 1
                    node_logger.error(
                        "filter decision failed",
                        tweet_id=getattr(tweet, "id", None),
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )

            node_logger.info("filter node complete", filtered_count=len(filtered_tweets))
            return {"filtered_tweets": filtered_tweets, "error_count": error_count}
        except Exception as exc:
            node_logger.error("filter node failed", error=str(exc), error_type=type(exc).__name__)
            return {"filtered_tweets": [], "error_count": error_count + 1}

    def _judge_node(self, state: AgentState) -> dict:
        node_logger = self.logger.bind(node="judge")
        judged_tweets = []
        error_count = state.get("error_count", 0)

        try:
            filtered_tweets = state.get("filtered_tweets", [])
            node_logger.info("judge node start", tweet_count=len(filtered_tweets))
            for tweet in filtered_tweets:
                try:
                    result = self._run_async(self.llm_client.judge_tweet(tweet.text, tweet.author_handle))
                    if result.is_hiring and result.confidence > 0.7:
                        judged_tweets.append((tweet, result))
                        node_logger.debug(
                            "tweet accepted by judge",
                            tweet_id=tweet.id,
                            confidence=result.confidence,
                            company=result.company,
                            role=result.role,
                        )
                    else:
                        node_logger.debug(
                            "tweet rejected by judge",
                            tweet_id=tweet.id,
                            confidence=result.confidence,
                            is_hiring=result.is_hiring,
                        )
                except Exception as exc:
                    error_count += 1
                    node_logger.error(
                        "judge decision failed",
                        tweet_id=getattr(tweet, "id", None),
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )

            node_logger.info("judge node complete", judged_count=len(judged_tweets))
            return {"judged_tweets": judged_tweets, "error_count": error_count}
        except Exception as exc:
            node_logger.error("judge node failed", error=str(exc), error_type=type(exc).__name__)
            return {"judged_tweets": [], "error_count": error_count + 1}

    def _notify_node(self, state: AgentState) -> dict:
        node_logger = self.logger.bind(node="notify")
        notifications_sent = state.get("notifications_sent", 0)
        error_count = state.get("error_count", 0)

        try:
            judged_tweets = state.get("judged_tweets", [])
            node_logger.info("notify node start", judged_count=len(judged_tweets))
            for tweet, judge in judged_tweets:
                try:
                    alert_message = format_hiring_alert(tweet, judge)
                    message_sid = self.whatsapp_client.send_notification(alert_message)
                    self.deduplicator.mark_seen(tweet, judge, notified=True)
                    notifications_sent += 1
                    node_logger.info(
                        "notification sent",
                        tweet_id=tweet.id,
                        message_sid=message_sid,
                    )
                except Exception as exc:
                    error_count += 1
                    node_logger.error(
                        "notification failed",
                        tweet_id=getattr(tweet, "id", None),
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )

            node_logger.info("notify node complete", notifications_sent=notifications_sent)
            return {"notifications_sent": notifications_sent, "error_count": error_count}
        except Exception as exc:
            node_logger.error("notify node failed", error=str(exc), error_type=type(exc).__name__)
            return {"notifications_sent": notifications_sent, "error_count": error_count + 1}

    def _sleep_node(self, state: AgentState) -> dict:
        node_logger = self.logger.bind(node="sleep")
        try:
            last_run = datetime.datetime.utcnow().isoformat()
            node_logger.info("sleep node complete", last_run=last_run)
            return {"last_run": last_run}
        except Exception as exc:
            node_logger.error("sleep node failed", error=str(exc), error_type=type(exc).__name__)
            return {"last_run": datetime.datetime.utcnow().isoformat(), "error_count": state.get("error_count", 0) + 1}

    def compile_graph(self) -> StateGraph:
        builder = StateGraph(AgentState)
        builder.add_node("search", self._search_node)
        builder.add_node("filter", self._filter_node)
        builder.add_node("judge", self._judge_node)
        builder.add_node("notify", self._notify_node)
        builder.add_node("sleep", self._sleep_node)

        builder.set_entry_point("search")
        builder.add_edge("search", "filter")
        builder.add_edge("filter", "judge")
        builder.add_edge("judge", "notify")
        builder.add_edge("notify", "sleep")
        builder.add_edge("sleep", END)

        checkpointer = SqliteSaver.from_conn_string("data/hiring_agent_graph.sqlite")
        return builder.compile(checkpointer=checkpointer)

    def run_once(self) -> dict:
        initial_state: AgentState = {
            "tweets": [],
            "filtered_tweets": [],
            "judged_tweets": [],
            "notifications_sent": 0,
            "error_count": 0,
            "last_run": None,
        }

        self.logger.info("running hiring agent once")
        final_state = self.graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": datetime.datetime.utcnow().isoformat()}},
        )
        self.logger.info(
            "hiring agent run complete",
            notifications_sent=final_state.get("notifications_sent", 0),
            error_count=final_state.get("error_count", 0),
            last_run=final_state.get("last_run"),
        )
        return final_state