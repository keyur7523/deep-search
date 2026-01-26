"""
Rate limiting middleware using token bucket algorithm.

Features:
- In-memory rate limiting (suitable for single-instance deployments)
- Per-user and per-endpoint rate limits
- Configurable limits via environment variables
- Automatic cleanup of stale buckets

For distributed deployments, consider using Redis-based rate limiting.

Usage:
    from middleware.rate_limit import rate_limit_dependency

    @app.post("/runs")
    async def create_run(
        request: Request,
        _: None = Depends(rate_limit_dependency("create_run", max_requests=10, window_seconds=60))
    ):
        ...
"""

import os
import time
import asyncio
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from fastapi import Request, HTTPException, Depends

logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: float, limit: int, window: int):
        super().__init__(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded. Maximum {limit} requests per {window} seconds.",
                "retry_after": retry_after
            },
            headers={"Retry-After": str(int(retry_after))}
        )


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: int  # Maximum tokens (burst capacity)
    refill_rate: float  # Tokens added per second
    tokens: float = field(default=0.0)
    last_update: float = field(default_factory=time.time)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            Tuple of (success, wait_time_if_failed)
        """
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        else:
            # Calculate wait time until enough tokens are available
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            return False, wait_time


class RateLimiter:
    """
    In-memory rate limiter using token bucket algorithm.

    Thread-safe for use with asyncio.
    """

    def __init__(self, cleanup_interval: int = 300):
        """
        Args:
            cleanup_interval: Seconds between cleanup of stale buckets
        """
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        tokens: int = 1
    ) -> Tuple[bool, float]:
        """
        Check if a request is allowed under the rate limit.

        Args:
            key: Unique identifier for the rate limit (e.g., "user_123:endpoint")
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds
            tokens: Number of tokens to consume (default 1)

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        async with self._lock:
            # Cleanup stale buckets periodically
            await self._maybe_cleanup()

            # Get or create bucket for this key
            if key not in self._buckets:
                # refill_rate = max_requests / window_seconds
                # This ensures the bucket refills to max_requests over window_seconds
                self._buckets[key] = TokenBucket(
                    capacity=max_requests,
                    refill_rate=max_requests / window_seconds
                )

            bucket = self._buckets[key]
            return bucket.consume(tokens)

    async def _maybe_cleanup(self):
        """Clean up stale buckets to prevent memory growth."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now

        # Remove buckets that haven't been used and are at full capacity
        stale_keys = []
        for key, bucket in self._buckets.items():
            # If bucket is full and hasn't been used in cleanup_interval, remove it
            if bucket.tokens >= bucket.capacity:
                elapsed = now - bucket.last_update
                if elapsed > self._cleanup_interval:
                    stale_keys.append(key)

        for key in stale_keys:
            del self._buckets[key]

        if stale_keys:
            logger.debug(f"Cleaned up {len(stale_keys)} stale rate limit buckets")

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            "active_buckets": len(self._buckets),
            "last_cleanup": self._last_cleanup
        }


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


# ============= Default Rate Limits =============

# Environment-configurable defaults
DEFAULT_RATE_LIMIT = int(os.getenv("RATE_LIMIT_DEFAULT", "60"))  # requests per minute
DEFAULT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

# Endpoint-specific limits
RATE_LIMITS = {
    "create_run": {
        "max_requests": int(os.getenv("RATE_LIMIT_CREATE_RUN", "10")),
        "window_seconds": 60
    },
    "create_project": {
        "max_requests": int(os.getenv("RATE_LIMIT_CREATE_PROJECT", "20")),
        "window_seconds": 60
    },
    "s3_presign": {
        "max_requests": int(os.getenv("RATE_LIMIT_S3_PRESIGN", "30")),
        "window_seconds": 60
    },
    "default": {
        "max_requests": DEFAULT_RATE_LIMIT,
        "window_seconds": DEFAULT_WINDOW
    }
}


# ============= FastAPI Dependencies =============

def get_client_identifier(request: Request) -> str:
    """
    Extract client identifier from request for rate limiting.

    Priority:
    1. Authenticated user ID
    2. API key
    3. X-Forwarded-For header (for proxied requests)
    4. Client IP address
    """
    # Check for authenticated user
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.sub}"

    # Check for API key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Hash the API key for privacy
        import hashlib
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return f"api_key:{key_hash}"

    # Use IP address as fallback
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    return f"ip:{client_ip}"


def rate_limit_dependency(
    endpoint_name: Optional[str] = None,
    max_requests: Optional[int] = None,
    window_seconds: Optional[int] = None
):
    """
    Create a rate limit dependency for FastAPI endpoints.

    Args:
        endpoint_name: Name of the endpoint for looking up configured limits
        max_requests: Override max requests (uses config if not provided)
        window_seconds: Override window (uses config if not provided)

    Returns:
        FastAPI dependency function

    Usage:
        @app.post("/runs")
        async def create_run(
            _: None = Depends(rate_limit_dependency("create_run"))
        ):
            ...

        # Or with custom limits:
        @app.post("/expensive")
        async def expensive_operation(
            _: None = Depends(rate_limit_dependency(max_requests=5, window_seconds=60))
        ):
            ...
    """

    async def dependency(request: Request) -> None:
        # Get rate limit configuration
        config = RATE_LIMITS.get(endpoint_name, RATE_LIMITS["default"])
        limit = max_requests or config["max_requests"]
        window = window_seconds or config["window_seconds"]

        # Build rate limit key
        client_id = get_client_identifier(request)
        key = f"{client_id}:{endpoint_name or 'default'}"

        # Check rate limit
        limiter = get_rate_limiter()
        allowed, retry_after = await limiter.is_allowed(key, limit, window)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_id} on {endpoint_name or 'default'}")
            raise RateLimitExceeded(retry_after, limit, window)

    return dependency


# ============= Middleware (Alternative Approach) =============

async def rate_limit_middleware(request: Request, call_next):
    """
    Global rate limiting middleware.

    Apply this to all requests with a default limit.
    Use the dependency approach for endpoint-specific limits.
    """
    # Skip rate limiting for health checks
    if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
        return await call_next(request)

    client_id = get_client_identifier(request)
    key = f"{client_id}:global"

    limiter = get_rate_limiter()
    config = RATE_LIMITS["default"]
    allowed, retry_after = await limiter.is_allowed(
        key,
        config["max_requests"],
        config["window_seconds"]
    )

    if not allowed:
        logger.warning(f"Global rate limit exceeded for {client_id}")
        raise RateLimitExceeded(retry_after, config["max_requests"], config["window_seconds"])

    return await call_next(request)
