import re

from src.clients.x_reverse_client import Tweet


HIRING_KEYWORDS = [
    "hiring",
    "join us",
    "join our team",
    "we're hiring",
    "were hiring",
    "apply now",
    "open position",
    "open roles",
    "recruiting",
    "looking for",
]

INTERN_KEYWORDS = [
    "intern",
    "internship",
    "sde intern",
    "swe intern",
    "software engineer intern",
    "summer intern",
    "winter intern",
]

SPAM_KEYWORDS = [
    "crypto",
    "nft",
    "web3",
    "blockchain",
    "airdrop",
    "giveaway",
    "whitelist",
    "mint",
    "token",
    "$",
    "follow for follow",
    "f4f",
]


def cheap_filter(tweet: Tweet) -> bool:
    """
    Lightweight pre-filter for tweets before LLM judgment.
    
    Returns True if the tweet should be processed further (passes all filters).
    Returns False if the tweet should be dropped.
    
    Filters:
    - Text length must be > 20 characters
    - Text must contain at least one HIRING_KEYWORD OR one INTERN_KEYWORD
    - Text must NOT contain any SPAM_KEYWORD
    - Must not be a retweet
    - Author handle must not contain spam terms
    
    Args:
        tweet: Tweet object to filter
        
    Returns:
        bool: True if tweet passes filter, False otherwise
    """
    # Rule e: Text length must be > 20 characters
    if len(tweet.text) <= 20:
        return False
    
    text_lower = tweet.text.lower()
    
    # Rule a: Must contain at least one HIRING_KEYWORD OR one INTERN_KEYWORD
    has_hiring = any(keyword in text_lower for keyword in HIRING_KEYWORDS)
    has_intern = any(keyword in text_lower for keyword in INTERN_KEYWORDS)
    
    if not (has_hiring or has_intern):
        return False
    
    # Rule b: Must NOT contain any SPAM_KEYWORD
    has_spam = any(keyword in text_lower for keyword in SPAM_KEYWORDS)
    if has_spam:
        return False
    
    # Rule c: Must not be a retweet
    if tweet.is_retweet:
        return False
    
    # Rule f: Author handle must not contain spam terms
    handle_lower = tweet.author_handle.lower()
    spam_terms = {"bot", "spam", "promo"}
    if any(term in handle_lower for term in spam_terms):
        return False
    
    # Rule d: is_reply is optional (allow by default)
    
    return True
