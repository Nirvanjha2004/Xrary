"""Thread-safe rate limiter utilities for API self-throttling."""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
	"""A simple fixed-window rate limiter.

	This limiter is suitable for client-side self-throttling, such as gating
	outbound requests in `XReverseClient`.
	"""

	def __init__(self, max_requests: int, window_seconds: int):
		if max_requests <= 0:
			raise ValueError("max_requests must be > 0")
		if window_seconds <= 0:
			raise ValueError("window_seconds must be > 0")

		self.max_requests = max_requests
		self.window_seconds = window_seconds
		self._lock = threading.Lock()
		self._timestamps: deque[float] = deque()

	def acquire(self) -> bool:
		"""Return True if a request is allowed in the current window."""
		now = time.monotonic()
		with self._lock:
			self._evict_expired(now)
			if len(self._timestamps) >= self.max_requests:
				return False
			self._timestamps.append(now)
			return True

	def wait_time(self) -> float:
		"""Return seconds until the next request slot becomes available."""
		now = time.monotonic()
		with self._lock:
			self._evict_expired(now)
			if len(self._timestamps) < self.max_requests:
				return 0.0

			oldest = self._timestamps[0]
			remaining = self.window_seconds - (now - oldest)
			return max(0.0, remaining)

	def _evict_expired(self, now: float) -> None:
		cutoff = now - self.window_seconds
		while self._timestamps and self._timestamps[0] <= cutoff:
			self._timestamps.popleft()


__all__ = ["RateLimiter"]
