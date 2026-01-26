"""
Structured error handling for the Deep Search API.

Provides:
- Standardized error response format
- Error codes for client handling
- Graceful degradation strategies
- Global exception handler

Usage:
    from middleware.errors import (
        APIError,
        ErrorCode,
        create_error_response,
        graceful_fallback
    )

    # Raise structured errors
    raise APIError(
        code=ErrorCode.VALIDATION_ERROR,
        message="Invalid project ID format",
        details={"field": "projectId", "received": value}
    )

    # Use graceful fallback
    result = await graceful_fallback(
        primary=fetch_from_api,
        fallback=get_cached_version,
        error_message="API unavailable, using cached data"
    )
"""

import logging
import traceback
from typing import Any, Dict, Optional, Callable, TypeVar
from enum import Enum
from dataclasses import dataclass, asdict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Authentication & Authorization (1xxx)
    AUTH_REQUIRED = "AUTH_1001"
    TOKEN_EXPIRED = "AUTH_1002"
    TOKEN_INVALID = "AUTH_1003"
    INSUFFICIENT_PERMISSIONS = "AUTH_1004"
    API_KEY_INVALID = "AUTH_1005"
    API_KEY_EXPIRED = "AUTH_1006"

    # Validation (2xxx)
    VALIDATION_ERROR = "VAL_2001"
    INVALID_PROJECT_ID = "VAL_2002"
    INVALID_RUN_ID = "VAL_2003"
    INVALID_CONFIG = "VAL_2004"
    INPUT_TOO_LONG = "VAL_2005"
    INVALID_URL = "VAL_2006"

    # Resource (3xxx)
    NOT_FOUND = "RES_3001"
    PROJECT_NOT_FOUND = "RES_3002"
    RUN_NOT_FOUND = "RES_3003"
    ALREADY_EXISTS = "RES_3004"
    CONFLICT = "RES_3005"

    # Rate Limiting (4xxx)
    RATE_LIMITED = "RATE_4001"
    QUOTA_EXCEEDED = "RATE_4002"

    # External Services (5xxx)
    LLM_UNAVAILABLE = "EXT_5001"
    LLM_RATE_LIMITED = "EXT_5002"
    SEARCH_UNAVAILABLE = "EXT_5003"
    DATABASE_ERROR = "EXT_5004"
    S3_ERROR = "EXT_5005"

    # Internal (6xxx)
    INTERNAL_ERROR = "INT_6001"
    SERVICE_DEGRADED = "INT_6002"
    MAINTENANCE = "INT_6003"

    # Business Logic (7xxx)
    RUN_ALREADY_COMPLETED = "BIZ_7001"
    RUN_ALREADY_CANCELLED = "BIZ_7002"
    INVALID_STATE_TRANSITION = "BIZ_7003"


@dataclass
class ErrorResponse:
    """Standardized error response structure."""
    error: bool = True
    code: str = ""
    message: str = ""
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    documentation_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {
            "error": self.error,
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.request_id:
            result["request_id"] = self.request_id
        if self.documentation_url:
            result["documentation_url"] = self.documentation_url
        return result


class APIError(HTTPException):
    """
    Structured API error that produces consistent responses.

    Usage:
        raise APIError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid input",
            status_code=400,
            details={"field": "topic", "issue": "too short"}
        )
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.error_code = code
        self.error_message = message
        self.error_details = details

        super().__init__(
            status_code=status_code,
            detail=ErrorResponse(
                code=code.value,
                message=message,
                details=details
            ).to_dict(),
            headers=headers
        )


def create_error_response(
    code: ErrorCode,
    message: str,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        code: Error code from ErrorCode enum
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details
        request: Optional request for extracting request ID

    Returns:
        JSONResponse with standardized error format
    """
    request_id = None
    if request:
        request_id = request.headers.get("X-Request-ID")

    response = ErrorResponse(
        code=code.value,
        message=message,
        details=details,
        request_id=request_id
    )

    return JSONResponse(
        status_code=status_code,
        content=response.to_dict()
    )


# ============= Graceful Degradation =============

class DegradedServiceError(Exception):
    """Raised when a service is operating in degraded mode."""

    def __init__(self, service: str, fallback_used: str, original_error: str):
        self.service = service
        self.fallback_used = fallback_used
        self.original_error = original_error
        super().__init__(f"{service} degraded: using {fallback_used}")


async def graceful_fallback(
    primary: Callable[..., T],
    fallback: Callable[..., T],
    *args,
    error_message: str = "Primary service unavailable",
    log_error: bool = True,
    **kwargs
) -> tuple[T, bool]:
    """
    Try primary function, fall back to secondary on failure.

    Args:
        primary: Primary async function to try
        fallback: Fallback async function if primary fails
        *args: Arguments to pass to both functions
        error_message: Message to log on fallback
        log_error: Whether to log the error
        **kwargs: Keyword arguments to pass to both functions

    Returns:
        Tuple of (result, was_fallback_used)
    """
    try:
        result = await primary(*args, **kwargs)
        return result, False
    except Exception as e:
        if log_error:
            logger.warning(f"{error_message}: {type(e).__name__}: {e}")

        try:
            result = await fallback(*args, **kwargs)
            return result, True
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
            raise


def with_fallback(fallback_value: T, error_message: str = "Using fallback value"):
    """
    Decorator that returns a fallback value on exception.

    Usage:
        @with_fallback(fallback_value=[], error_message="Search failed")
        async def search_papers(query: str) -> List[Dict]:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"{error_message}: {type(e).__name__}: {e}")
                return fallback_value
        return wrapper
    return decorator


class DegradationLevel(str, Enum):
    """Service degradation levels."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"


@dataclass
class ServiceStatus:
    """Status of an external service."""
    name: str
    level: DegradationLevel
    message: str = ""
    last_check: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class ServiceHealthTracker:
    """
    Track health of external services for degradation decisions.

    Usage:
        tracker = ServiceHealthTracker()
        tracker.update("llm", DegradationLevel.DEGRADED, "High latency")

        if tracker.should_use_fallback("llm"):
            # Use cached/fallback response
    """

    def __init__(self):
        self._services: Dict[str, ServiceStatus] = {}

    def update(
        self,
        service: str,
        level: DegradationLevel,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update service status."""
        import time
        self._services[service] = ServiceStatus(
            name=service,
            level=level,
            message=message,
            last_check=time.time(),
            details=details
        )

    def get_status(self, service: str) -> Optional[ServiceStatus]:
        """Get current status of a service."""
        return self._services.get(service)

    def should_use_fallback(self, service: str) -> bool:
        """Check if fallback should be used for a service."""
        status = self._services.get(service)
        if not status:
            return False
        return status.level in [DegradationLevel.CRITICAL, DegradationLevel.UNAVAILABLE]

    def all_statuses(self) -> Dict[str, ServiceStatus]:
        """Get all service statuses."""
        return self._services.copy()


# Global service health tracker
service_health = ServiceHealthTracker()


# ============= Exception Handlers =============

def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers for the FastAPI app.

    Call this during app initialization:
        setup_exception_handlers(app)
    """

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        """Handle structured API errors."""
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
            headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            errors.append({
                "field": loc,
                "message": error["msg"],
                "type": error["type"]
            })

        return create_error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed",
            status_code=422,
            details={"errors": errors},
            request=request
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException
    ) -> JSONResponse:
        """Handle standard HTTP exceptions with consistent format."""
        # Map status codes to error codes
        code_map = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.AUTH_REQUIRED,
            403: ErrorCode.INSUFFICIENT_PERMISSIONS,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            429: ErrorCode.RATE_LIMITED,
            500: ErrorCode.INTERNAL_ERROR,
            503: ErrorCode.SERVICE_DEGRADED,
        }

        error_code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

        # Handle detail that's already structured
        if isinstance(exc.detail, dict):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
                headers=getattr(exc, "headers", None)
            )

        return create_error_response(
            code=error_code,
            message=str(exc.detail),
            status_code=exc.status_code,
            request=request
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """
        Handle unexpected exceptions.

        Logs the full traceback but returns a safe message to clients.
        """
        # Log full details for debugging
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: "
            f"{type(exc).__name__}: {exc}"
        )
        logger.error(traceback.format_exc())

        # Return safe message to client
        return create_error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred. Please try again later.",
            status_code=500,
            details={
                "error_type": type(exc).__name__,
                # Only include error message in non-production
                # "error_detail": str(exc)  # Uncomment for debugging
            },
            request=request
        )


# ============= Convenience Functions =============

def not_found(resource: str, resource_id: str) -> APIError:
    """Create a not found error."""
    return APIError(
        code=ErrorCode.NOT_FOUND,
        message=f"{resource} not found",
        status_code=404,
        details={"resource": resource, "id": resource_id}
    )


def validation_error(field: str, message: str, received: Any = None) -> APIError:
    """Create a validation error."""
    details = {"field": field, "message": message}
    if received is not None:
        details["received"] = str(received)[:100]

    return APIError(
        code=ErrorCode.VALIDATION_ERROR,
        message=f"Validation error: {message}",
        status_code=400,
        details=details
    )


def rate_limited(retry_after: int) -> APIError:
    """Create a rate limit error."""
    return APIError(
        code=ErrorCode.RATE_LIMITED,
        message=f"Rate limit exceeded. Try again in {retry_after} seconds.",
        status_code=429,
        details={"retry_after": retry_after},
        headers={"Retry-After": str(retry_after)}
    )


def service_unavailable(service: str, message: str = "Service temporarily unavailable") -> APIError:
    """Create a service unavailable error."""
    return APIError(
        code=ErrorCode.SERVICE_DEGRADED,
        message=message,
        status_code=503,
        details={"service": service}
    )
