from src.clients.llm_client import JudgeResult
from src.clients.x_reverse_client import Tweet
from src.storage.database import SeenTweet, get_db, init_db


class Deduplicator:
	def __init__(self, session_factory=get_db):
		init_db()
		self.session_factory = session_factory

	def _open_session(self):
		generator = self.session_factory()
		session = next(generator)
		return session, generator

	def is_seen(self, tweet_id: str) -> bool:
		session, generator = self._open_session()
		try:
			existing = session.query(SeenTweet).filter(SeenTweet.tweet_id == tweet_id).first()
			return existing is not None
		finally:
			generator.close()

	def mark_seen(
		self,
		tweet: Tweet,
		judge: JudgeResult | None = None,
		notified: bool = True,
	) -> None:
		session, generator = self._open_session()
		try:
			existing = session.query(SeenTweet).filter(SeenTweet.tweet_id == tweet.id).first()
			if existing is None:
				existing = SeenTweet(
					tweet_id=tweet.id,
					tweet_text=tweet.text,
					author_handle=tweet.author_handle,
					notified=notified,
					confidence_score=judge.confidence if judge is not None else None,
					company=judge.company if judge is not None else None,
					role=judge.role if judge is not None else None,
				)
				session.add(existing)
			else:
				existing.tweet_text = tweet.text
				existing.author_handle = tweet.author_handle
				existing.notified = notified
				existing.confidence_score = judge.confidence if judge is not None else existing.confidence_score
				existing.company = judge.company if judge is not None else existing.company
				existing.role = judge.role if judge is not None else existing.role

			session.commit()
		except Exception:
			session.rollback()
			raise
		finally:
			generator.close()
