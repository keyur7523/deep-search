"""
Middleware modules for Deep Search API.
"""

from .rate_limit import RateLimiter, rate_limit_dependency, RateLimitExceeded
from .validation import (
    ValidationError,
    sanitize_topic,
    sanitize_goal,
    sanitize_url,
    validate_config,
    ValidatedNewProject,
    ValidatedCreateRunRequest,
)
from .audit import (
    audit_log,
    audit_action,
    log_auth_success,
    log_auth_failure,
    log_run_created,
    log_run_deleted,
    log_security_event,
    AuditEvent,
    AuditCategory,
)
from .errors import (
    APIError,
    ErrorCode,
    ErrorResponse,
    create_error_response,
    graceful_fallback,
    with_fallback,
    service_health,
    setup_exception_handlers,
    not_found,
    validation_error,
    rate_limited,
    service_unavailable,
)

__all__ = [
    # Rate limiting
    "RateLimiter",
    "rate_limit_dependency",
    "RateLimitExceeded",
    # Validation
    "ValidationError",
    "sanitize_topic",
    "sanitize_goal",
    "sanitize_url",
    "validate_config",
    "ValidatedNewProject",
    "ValidatedCreateRunRequest",
    # Audit logging
    "audit_log",
    "audit_action",
    "log_auth_success",
    "log_auth_failure",
    "log_run_created",
    "log_run_deleted",
    "log_security_event",
    "AuditEvent",
    "AuditCategory",
    # Error handling
    "APIError",
    "ErrorCode",
    "ErrorResponse",
    "create_error_response",
    "graceful_fallback",
    "with_fallback",
    "service_health",
    "setup_exception_handlers",
    "not_found",
    "validation_error",
    "rate_limited",
    "service_unavailable",
]
