"""Retry decorator for resilient API calls."""

import httpx
from typing import Any, Callable, TypeVar

from tenacity import (
    retry as tenacity_retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep,
    RetryCallState,
)
import structlog

logger = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempts with structlog."""
    exception = None
    if retry_state.outcome and retry_state.outcome.failed:
        exception = str(retry_state.outcome.exception())
    
    logger.warning(
        "retry_attempt",
        attempt_number=retry_state.attempt_number,
        seconds_since_start=retry_state.seconds_since_start,
        exception=exception,
    )


def retry(
    max_attempts: int = 3,
    backoff_multiplier: float = 1.0,
    max_wait: int = 30,
) -> Callable[[F], F]:
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        backoff_multiplier: Multiplier for exponential backoff (default: 1.0)
        max_wait: Maximum wait time between retries in seconds (default: 30)
    
    Returns:
        Decorated function that retries on failure
    
    Retries on:
        - httpx.HTTPStatusError
        - httpx.ConnectError
        - TimeoutError
    """
    return tenacity_retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=backoff_multiplier,
            min=2,
            max=max_wait,
        ),
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.ConnectError, TimeoutError)
        ),
        before_sleep=before_sleep(_log_retry_attempt),
        reraise=True,
    )


__all__ = ["retry"]
