import json
import re
from datetime import datetime
from typing import Optional

import httpx
import structlog
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from src.config import Settings


logger = structlog.get_logger()

SEARCH_TIMELINE_GRAPHQL_ID = "KqFemWADwSm5Jq_bWzZqkQ"


class TweetMetrics(BaseModel):
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0


class Tweet(BaseModel):
    id: str
    text: str
    author_handle: str
    author_name: str
    created_at: datetime
    metrics: TweetMetrics
    urls: list[str] = []
    is_reply: bool = False
    is_retweet: bool = False


class XRateLimitError(Exception):
    """Raised when X API returns rate limit (429) status."""
    pass


class XAuthError(Exception):
    """Raised when X API returns authentication error."""
    pass


class XGraphQLError(Exception):
    """Raised when X GraphQL response contains errors."""
    pass


class XReverseClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = structlog.get_logger()
        
        cookies = {
            "auth_token": settings.x_auth_token,
            "ct0": settings.x_ct0,
        }
        
        headers = {
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAA%2F%2F%2F%2F%2F%2FwEaABaXgaaSZ66jgGaCR%2B9Og8iPB4%2F1o%2F%2FM0Y%3DagIJVrCeBZSCyMCsTMZo7p0awVV20wnDAcHmv1GX5A19MR5qKw",
            "x-csrf-token": settings.x_ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en",
        }
        
        self.client = httpx.AsyncClient(
            cookies=cookies,
            headers=headers,
            timeout=30.0,
        )

    async def _parse_twitter_datetime(self, date_str: str) -> datetime:
        """Parse Twitter's datetime format: 'Mon Jan 02 15:04:05 +0000 2006'"""
        try:
            return datetime.strptime(date_str, "%a %b %d %H:%M:%S +0000 %Y")
        except (ValueError, TypeError):
            self.logger.warning("failed to parse twitter datetime", date_str=date_str)
            return datetime.utcnow()

    async def _extract_urls_from_entities(self, entities: Optional[dict]) -> list[str]:
        """Extract expanded URLs from tweet entities."""
        urls = []
        if not entities or "urls" not in entities:
            return urls
        
        for url_obj in entities.get("urls", []):
            if "expanded_url" in url_obj:
                urls.append(url_obj["expanded_url"])
        
        return urls

    async def _parse_tweet_from_legacy(self, legacy: dict, tweet_result: dict) -> Optional[Tweet]:
        """Parse a single tweet from GraphQL legacy data."""
        try:
            tweet_id = legacy.get("id_str", "")
            text = legacy.get("full_text", "")
            
            if not tweet_id or not text:
                return None
            
            user = legacy.get("user", {})
            author_handle = user.get("screen_name", "")
            author_name = user.get("name", "")
            
            created_at_str = legacy.get("created_at", "")
            created_at = await self._parse_twitter_datetime(created_at_str)
            
            metrics = TweetMetrics(
                retweet_count=legacy.get("retweet_count", 0),
                like_count=legacy.get("favorite_count", 0),
                reply_count=legacy.get("reply_count", 0),
            )
            
            urls = await self._extract_urls_from_entities(legacy.get("entities"))
            
            is_reply = legacy.get("in_reply_to_status_id_str") is not None
            is_retweet = "retweeted_status_id_str" in legacy
            
            return Tweet(
                id=tweet_id,
                text=text,
                author_handle=author_handle,
                author_name=author_name,
                created_at=created_at,
                metrics=metrics,
                urls=urls,
                is_reply=is_reply,
                is_retweet=is_retweet,
            )
        except Exception as e:
            self.logger.warning("failed to parse tweet from legacy", error=str(e), legacy=legacy)
            return None

    async def _parse_graphql_response(self, response_json: dict) -> list[Tweet]:
        """Parse the nested GraphQL response and extract tweets."""
        tweets = []
        
        # Check for GraphQL errors
        if "errors" in response_json:
            self.logger.error("graphql response contains errors", errors=response_json["errors"])
            raise XGraphQLError(f"GraphQL errors: {response_json['errors']}")
        
        try:
            data = response_json.get("data", {})
            search_by_raw_query = data.get("search_by_raw_query", {})
            search_timeline = search_by_raw_query.get("search_timeline", {})
            timeline = search_timeline.get("timeline", {})
            instructions = timeline.get("instructions", [])
            
            for instruction in instructions:
                if instruction.get("type") != "TimelineAddEntries":
                    continue
                
                entries = instruction.get("entries", [])
                for entry in entries:
                    content = entry.get("content", {})
                    item_content = content.get("itemContent", {})
                    tweet_results = item_content.get("tweet_results", {})
                    result = tweet_results.get("result", {})
                    
                    if result.get("__typename") == "Tweet":
                        legacy = result.get("legacy", {})
                        tweet = await self._parse_tweet_from_legacy(legacy, result)
                        if tweet:
                            tweets.append(tweet)
        
        except Exception as e:
            self.logger.warning("error parsing graphql response structure", error=str(e))
            # Return what we've collected so far rather than failing completely
        
        return tweets

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=lambda e: isinstance(e, (httpx.HTTPStatusError, httpx.ConnectError, XRateLimitError)),
    )
    async def search_tweets(self, query: str, max_results: int = 20) -> list[Tweet]:
        """
        Search tweets on X using the reverse-engineered GraphQL endpoint.
        
        Args:
            query: The search query string
            max_results: Maximum number of tweets to return (default 20)
        
        Returns:
            List of Tweet objects matching the query
        
        Raises:
            XRateLimitError: If the API returns 429 (rate limited)
            XAuthError: If the API returns 401/403 (authentication error)
            XGraphQLError: If the GraphQL response contains errors
        """
        self.logger.info("searching tweets", query=query, max_results=max_results)
        
        # Build the GraphQL payload
        variables = {
            "rawQuery": query,
            "count": max_results,
            "product": "Latest",
        }
        
        payload = {
            "variables": variables,
            "features": {
                "rweb_tipjar_consumption_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "communities_web_enable_tweet_community_results": False,
                "c9s_tweet_anatomy_moderization_enabled": True,
                "articles_preview_enabled": True,
                "tweetypie_unmention_optimization_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "responsive_web_twitter_article_tweet_consumption_enabled": False,
                "tweet_awards_web_tipping_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_controlled_entities_enabled": True,
                "tweet_with_visibility_results_prefer_gql_limited_count_enabled": False,
                "interactive_text_enabled": True,
                "responsive_web_text_conversations_enabled": False,
                "longform_notetweets_rich_text_consumption_enabled": True,
                "longform_notetweets_are_collapsible_enabled": True,
                "responsive_web_enhance_cards_enabled": False,
            }
        }
        
        url = f"https://twitter.com/i/api/graphql/{SEARCH_TIMELINE_GRAPHQL_ID}/SearchTimeline"
        
        try:
            response = await self.client.post(url, json=payload)
            
            # Handle rate limiting
            if response.status_code == 429:
                self.logger.error("rate limited by X API")
                raise XRateLimitError("X API rate limit exceeded")
            
            # Handle authentication errors
            if response.status_code in (401, 403):
                self.logger.error("authentication failed", status_code=response.status_code)
                raise XAuthError(f"Authentication failed with status {response.status_code}")
            
            response.raise_for_status()
            
            response_json = response.json()
            tweets = await self._parse_graphql_response(response_json)
            
            self.logger.info("search completed successfully", query=query, tweet_count=len(tweets))
            return tweets
        
        except XRateLimitError:
            raise
        except XAuthError:
            raise
        except XGraphQLError:
            raise
        except httpx.HTTPStatusError as e:
            self.logger.error("http error during search", status_code=e.response.status_code, error=str(e))
            raise
        except httpx.ConnectError as e:
            self.logger.error("connection error during search", error=str(e))
            raise
        except Exception as e:
            self.logger.error("unexpected error during search", error=str(e), error_type=type(e).__name__)
            raise
