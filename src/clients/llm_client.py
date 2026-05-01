import json

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from src.config import Settings


logger = structlog.get_logger()


class JudgeResult(BaseModel):
    is_hiring: bool
    confidence: float = Field(ge=0.0, le=1.0)
    company: str | None = None
    role: str | None = None
    location: str | None = None
    apply_link: str | None = None


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.logger = structlog.get_logger()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def judge_tweet(self, tweet_text: str, author: str) -> JudgeResult:
        """
        Judge whether a tweet is a genuine SDE intern hiring post.

        Args:
            tweet_text: The tweet content
            author: Twitter handle of the author

        Returns:
            JudgeResult containing classification and extracted metadata

        On any OpenAI error, logs the error and returns a safe default:
        JudgeResult(is_hiring=False, confidence=0.0)
        """
        system_prompt = (
            "You are a hiring post classifier. Analyze tweets for SDE/software engineering "
            "intern hiring opportunities. Return ONLY valid JSON matching the schema."
        )

        user_prompt = (
            f"Tweet by @{author}:\n{tweet_text}\n\n"
            "Classify this tweet. Is it a genuine SDE intern hiring post? "
            "Return JSON with: is_hiring (bool), confidence (0-1), company (str or null), "
            "role (str or null), location (str or null), apply_link (str or null if no URL in tweet)."
        )

        self.logger.info(
            "judging tweet",
            author=author,
            tweet_preview=tweet_text[:100],
            model=self.model,
        )

        try:
            # Try to use structured output parsing if available
            try:
                response = await self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=JudgeResult,
                )
                result = response.choices[0].message.parsed
            except (AttributeError, NotImplementedError):
                # Fall back to JSON mode if parse() is not available
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )
                response_text = response.choices[0].message.content
                response_json = json.loads(response_text)
                result = JudgeResult(**response_json)

            # Apply confidence override: if confidence < 0.7, force is_hiring to False
            if result.confidence < 0.7:
                self.logger.info(
                    "confidence below threshold, forcing is_hiring=False",
                    author=author,
                    original_is_hiring=result.is_hiring,
                    confidence=result.confidence,
                )
                result.is_hiring = False

            self.logger.info(
                "tweet judged successfully",
                author=author,
                is_hiring=result.is_hiring,
                confidence=result.confidence,
                company=result.company,
                role=result.role,
            )

            return result

        except Exception as e:
            self.logger.error(
                "error judging tweet",
                author=author,
                tweet_preview=tweet_text[:100],
                error=str(e),
                error_type=type(e).__name__,
            )
            return JudgeResult(is_hiring=False, confidence=0.0)
