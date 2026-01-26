"""
Retry utilities with exponential backoff for resilient API calls.

Features:
- Exponential backoff with jitter
- Configurable retry conditions
- Circuit breaker pattern support
- Rate limit handling (429 responses)
"""

import asyncio
import random
import logging
import time
from typing import Callable, TypeVar, Optional, Set, Any
from functools import wraps
import httpx

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_status_codes: Optional[Set[int]] = None,
        retryable_exceptions: Optional[tuple] = None
    ):
        """
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential growth (2.0 = doubling)
            jitter: Add random jitter to prevent thundering herd
            retryable_status_codes: HTTP status codes that trigger retry (default: 429, 500-599)
            retryable_exceptions: Exception types that trigger retry
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_status_codes = retryable_status_codes or {429, 500, 502, 503, 504}
        self.retryable_exceptions = retryable_exceptions or (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
            ConnectionError,
            asyncio.TimeoutError
        )


# Default configurations for different scenarios
DEFAULT_CONFIG = RetryConfig()
AGGRESSIVE_CONFIG = RetryConfig(max_retries=5, base_delay=2.0, max_delay=120.0)
GENTLE_CONFIG = RetryConfig(max_retries=2, base_delay=0.5, max_delay=10.0)


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for a given retry attempt using exponential backoff with jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    # Exponential backoff: base_delay * (exponential_base ^ attempt)
    delay = config.base_delay * (config.exponential_base ** attempt)

    # Cap at max delay
    delay = min(delay, config.max_delay)

    # Add jitter (0-10% of delay) to prevent thundering herd
    if config.jitter:
        jitter_amount = delay * random.uniform(0, 0.1)
        delay += jitter_amount

    return delay


async def retry_async(
    func: Callable[..., T],
    *args,
    config: RetryConfig = DEFAULT_CONFIG,
    operation_name: str = "operation",
    **kwargs
) -> T:
    """
    Execute an async function with retry logic.

    Args:
        func: Async function to execute
        *args: Positional arguments to pass to func
        config: Retry configuration
        operation_name: Name for logging purposes
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result of func

    Raises:
        Last exception if all retries fail
    """
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            if attempt > 0:
                logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
            return result

        except config.retryable_exceptions as e:
            last_exception = e
            if attempt < config.max_retries:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}/{config.max_retries + 1}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"{operation_name} failed after {config.max_retries + 1} attempts: {e}")
                raise

        except Exception as e:
            # Non-retryable exception
            logger.error(f"{operation_name} failed with non-retryable error: {e}")
            raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError(f"{operation_name} failed unexpectedly")


async def retry_http_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    config: RetryConfig = DEFAULT_CONFIG,
    operation_name: str = "HTTP request",
    **kwargs
) -> httpx.Response:
    """
    Execute an HTTP request with retry logic for transient failures.

    Handles:
    - Network errors (timeout, connection)
    - Rate limiting (429)
    - Server errors (500-599)

    Args:
        client: httpx AsyncClient instance
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        config: Retry configuration
        operation_name: Name for logging
        **kwargs: Additional arguments for httpx request

    Returns:
        httpx.Response object

    Raises:
        httpx.HTTPStatusError: If request fails after all retries
    """
    last_exception: Optional[Exception] = None
    last_response: Optional[httpx.Response] = None

    for attempt in range(config.max_retries + 1):
        try:
            response = await client.request(method, url, **kwargs)

            # Check if we should retry based on status code
            if response.status_code in config.retryable_status_codes:
                last_response = response

                if attempt < config.max_retries:
                    # Special handling for rate limiting
                    if response.status_code == 429:
                        # Check for Retry-After header
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = calculate_delay(attempt, config)
                        else:
                            delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"{operation_name} rate limited (429). "
                            f"Waiting {delay:.2f}s before retry..."
                        )
                    else:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"{operation_name} returned {response.status_code} "
                            f"(attempt {attempt + 1}/{config.max_retries + 1}). "
                            f"Retrying in {delay:.2f}s..."
                        )

                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"{operation_name} failed with status {response.status_code} "
                        f"after {config.max_retries + 1} attempts"
                    )

            return response

        except config.retryable_exceptions as e:
            last_exception = e

            if attempt < config.max_retries:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    f"{operation_name} error (attempt {attempt + 1}/{config.max_retries + 1}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"{operation_name} failed after {config.max_retries + 1} attempts: {e}")
                raise

    # Return last response if we have one (even if error status)
    if last_response:
        return last_response

    # Otherwise raise last exception
    if last_exception:
        raise last_exception

    raise RuntimeError(f"{operation_name} failed unexpectedly")


def with_retry(config: RetryConfig = DEFAULT_CONFIG, operation_name: Optional[str] = None):
    """
    Decorator to add retry logic to async functions.

    Usage:
        @with_retry(config=AGGRESSIVE_CONFIG, operation_name="Semantic Scholar API")
        async def search_papers(query: str) -> List[Dict]:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            name = operation_name or func.__name__
            return await retry_async(func, *args, config=config, operation_name=name, **kwargs)
        return wrapper
    return decorator


# ============= Circuit Breaker =============

class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests fail immediately
    - HALF_OPEN: Testing if service recovered

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_time=60)

        async def call_api():
            if not breaker.can_execute():
                raise ServiceUnavailableError("Circuit breaker open")
            try:
                result = await external_api_call()
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_time: float = 60.0,
        half_open_max_calls: int = 3
    ):
        """
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_time: Seconds to wait before allowing test calls
            half_open_max_calls: Number of test calls in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.half_open_max_calls = half_open_max_calls

        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        """Check if a request should be allowed through."""
        if self.state == self.CLOSED:
            return True

        if self.state == self.OPEN:
            # Check if recovery time has passed
            if self.last_failure_time and time.time() - self.last_failure_time >= self.recovery_time:
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN state")
                return True
            return False

        if self.state == self.HALF_OPEN:
            # Allow limited calls in half-open state
            return self.half_open_calls < self.half_open_max_calls

        return False

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == self.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self.state = self.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker recovered - transitioning to CLOSED state")
        elif self.state == self.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == self.HALF_OPEN:
            # Any failure in half-open reopens the circuit
            self.state = self.OPEN
            self.half_open_calls = 0
            logger.warning("Circuit breaker reopened after failure in HALF_OPEN state")

        elif self.state == self.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = self.OPEN
                logger.warning(
                    f"Circuit breaker OPEN after {self.failure_count} consecutive failures"
                )

    def time_until_recovery(self) -> float:
        """
        Get seconds until circuit breaker will attempt recovery.

        Returns:
            Seconds until half-open state, or 0 if already closed/half-open
        """
        if self.state != self.OPEN:
            return 0.0

        if not self.last_failure_time:
            return 0.0

        elapsed = time.time() - self.last_failure_time
        remaining = self.recovery_time - elapsed
        return max(0.0, remaining)

    def get_state(self) -> dict:
        """Get current circuit breaker state for monitoring."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "can_execute": self.can_execute(),
            "time_until_recovery": self.time_until_recovery()
        }
