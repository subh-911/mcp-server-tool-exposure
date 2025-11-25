"""
Rate limiting functionality for the MCP server.

This module implements a simple sliding window rate limiter to prevent
abuse and protect server resources.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import DefaultDict, List

from src.config import get_settings
from src.utils.errors import RateLimitError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter.

    This class implements rate limiting using a sliding window algorithm,
    tracking requests per identifier within a time window.
    """

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum requests per window (uses config if None)
            window_seconds: Time window in seconds (uses config if None)
        """
        settings = get_settings()
        self.max_requests = max_requests or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window
        self.requests: DefaultDict[str, List[float]] = defaultdict(list)
        self.lock = Lock()

        logger.info(
            "Rate limiter initialized",
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )

    def _clean_old_requests(self, identifier: str, now: float) -> None:
        """
        Remove requests outside the current time window.

        Args:
            identifier: Identifier for the client/resource
            now: Current timestamp
        """
        cutoff = now - self.window_seconds
        self.requests[identifier] = [
            timestamp
            for timestamp in self.requests[identifier]
            if timestamp > cutoff
        ]

    def check_rate_limit(self, identifier: str) -> None:
        """
        Check if a request is allowed under the rate limit.

        Args:
            identifier: Identifier for the client/resource (e.g., user ID, IP)

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        with self.lock:
            now = time.time()
            self._clean_old_requests(identifier, now)

            current_count = len(self.requests[identifier])

            if current_count >= self.max_requests:
                oldest_request = min(self.requests[identifier])
                reset_time = oldest_request + self.window_seconds
                wait_seconds = int(reset_time - now) + 1

                logger.warning(
                    "Rate limit exceeded",
                    identifier=identifier,
                    current_count=current_count,
                    max_requests=self.max_requests,
                    wait_seconds=wait_seconds,
                )

                raise RateLimitError(
                    message=f"Rate limit exceeded. Try again in {wait_seconds} seconds.",
                    details={
                        "identifier": identifier,
                        "current_count": current_count,
                        "max_requests": self.max_requests,
                        "window_seconds": self.window_seconds,
                        "retry_after_seconds": wait_seconds,
                    },
                )

            # Record this request
            self.requests[identifier].append(now)

            logger.debug(
                "Rate limit check passed",
                identifier=identifier,
                current_count=current_count + 1,
                max_requests=self.max_requests,
            )

    def get_remaining_requests(self, identifier: str) -> int:
        """
        Get the number of remaining requests for an identifier.

        Args:
            identifier: Identifier for the client/resource

        Returns:
            Number of remaining requests in the current window
        """
        with self.lock:
            now = time.time()
            self._clean_old_requests(identifier, now)
            current_count = len(self.requests[identifier])
            return max(0, self.max_requests - current_count)

    def reset(self, identifier: str | None = None) -> None:
        """
        Reset rate limit for an identifier or all identifiers.

        Args:
            identifier: Identifier to reset, or None to reset all
        """
        with self.lock:
            if identifier:
                self.requests.pop(identifier, None)
                logger.info("Rate limit reset for identifier", identifier=identifier)
            else:
                self.requests.clear()
                logger.info("Rate limit reset for all identifiers")

    def get_stats(self) -> dict:
        """
        Get statistics about current rate limiting state.

        Returns:
            Dictionary with rate limiting statistics
        """
        with self.lock:
            now = time.time()
            # Clean all old requests
            for identifier in list(self.requests.keys()):
                self._clean_old_requests(identifier, now)
                # Remove empty entries
                if not self.requests[identifier]:
                    del self.requests[identifier]

            return {
                "active_identifiers": len(self.requests),
                "total_requests_in_window": sum(
                    len(reqs) for reqs in self.requests.values()
                ),
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
            }


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
