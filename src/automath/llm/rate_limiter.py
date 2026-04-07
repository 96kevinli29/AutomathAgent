"""Token-bucket rate limiter for LLM API calls."""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Simple token-bucket rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 60, tokens_per_minute: int = 100_000):
        self.rpm = requests_per_minute
        self.tpm = tokens_per_minute
        self._request_times: list[float] = []
        self._token_counts: list[tuple[float, int]] = []
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1000) -> None:
        """Wait until rate limits allow another request."""
        async with self._lock:
            now = time.monotonic()

            # Clean old entries (older than 60 seconds)
            self._request_times = [t for t in self._request_times if now - t < 60]
            self._token_counts = [(t, c) for t, c in self._token_counts if now - t < 60]

            # Check request rate
            if len(self._request_times) >= self.rpm:
                wait_time = 60 - (now - self._request_times[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

            # Check token rate
            total_tokens = sum(c for _, c in self._token_counts)
            if total_tokens + estimated_tokens > self.tpm:
                oldest = min(t for t, _ in self._token_counts) if self._token_counts else now
                wait_time = 60 - (now - oldest)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

            # Record this request
            self._request_times.append(time.monotonic())
            self._token_counts.append((time.monotonic(), estimated_tokens))

    def record_usage(self, tokens: int) -> None:
        """Record actual token usage after a request completes."""
        now = time.monotonic()
        self._token_counts.append((now, tokens))
