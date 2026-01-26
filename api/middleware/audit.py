"""
Audit logging middleware for compliance and security monitoring.

Provides structured logging for sensitive operations:
- Authentication events (login, logout, failures)
- Resource creation/deletion (runs, projects)
- Configuration changes
- Administrative actions

Audit logs are written in JSON format for easy parsing by SIEM systems.

Usage:
    from middleware.audit import audit_log, AuditEvent, AuditCategory

    # Log an event
    await audit_log(
        event=AuditEvent.RUN_CREATED,
        user_id=user.sub,
        resource_id=run_id,
        details={"project_id": project_id, "mode": mode}
    )

    # Or use the decorator
    @audit_action(AuditEvent.PROJECT_DELETED)
    async def delete_project(project_id: str, user: User):
        ...
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable
from enum import Enum
from functools import wraps
from dataclasses import dataclass, asdict
from fastapi import Request

# Configure audit logger separately from application logs
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Add file handler for audit logs if configured
AUDIT_LOG_FILE = os.getenv("AUDIT_LOG_FILE")
if AUDIT_LOG_FILE:
    file_handler = logging.FileHandler(AUDIT_LOG_FILE)
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    audit_logger.addHandler(file_handler)

# Also log to stdout in JSON format
if os.getenv("AUDIT_LOG_STDOUT", "true").lower() == "true":
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(logging.Formatter('%(message)s'))
    audit_logger.addHandler(stdout_handler)


class AuditCategory(str, Enum):
    """Categories of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    ADMINISTRATIVE = "administrative"
    SECURITY = "security"
    SYSTEM = "system"


class AuditEvent(str, Enum):
    """Specific audit events to track."""
    # Authentication
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_EXPIRED = "auth.token.expired"
    AUTH_TOKEN_INVALID = "auth.token.invalid"

    # API Keys
    API_KEY_CREATED = "api_key.created"
    API_KEY_ROTATED = "api_key.rotated"
    API_KEY_REVOKED = "api_key.revoked"
    API_KEY_EXPIRED = "api_key.expired"

    # Runs
    RUN_CREATED = "run.created"
    RUN_DELETED = "run.deleted"
    RUN_CANCELLED = "run.cancelled"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"

    # Projects
    PROJECT_CREATED = "project.created"
    PROJECT_DELETED = "project.deleted"
    PROJECT_UPDATED = "project.updated"

    # Data Access
    DATA_EXPORTED = "data.exported"
    REPORT_GENERATED = "report.generated"
    SOURCES_ACCESSED = "sources.accessed"

    # Administrative
    CONFIG_CHANGED = "config.changed"
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"
    PERMISSIONS_CHANGED = "permissions.changed"

    # Security
    RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    SSRF_BLOCKED = "security.ssrf_blocked"
    VALIDATION_FAILED = "security.validation_failed"


# Map events to categories
EVENT_CATEGORIES = {
    AuditEvent.AUTH_LOGIN_SUCCESS: AuditCategory.AUTHENTICATION,
    AuditEvent.AUTH_LOGIN_FAILURE: AuditCategory.AUTHENTICATION,
    AuditEvent.AUTH_LOGOUT: AuditCategory.AUTHENTICATION,
    AuditEvent.AUTH_TOKEN_EXPIRED: AuditCategory.AUTHENTICATION,
    AuditEvent.AUTH_TOKEN_INVALID: AuditCategory.AUTHENTICATION,

    AuditEvent.API_KEY_CREATED: AuditCategory.ADMINISTRATIVE,
    AuditEvent.API_KEY_ROTATED: AuditCategory.ADMINISTRATIVE,
    AuditEvent.API_KEY_REVOKED: AuditCategory.ADMINISTRATIVE,
    AuditEvent.API_KEY_EXPIRED: AuditCategory.AUTHENTICATION,

    AuditEvent.RUN_CREATED: AuditCategory.DATA_MODIFICATION,
    AuditEvent.RUN_DELETED: AuditCategory.DATA_MODIFICATION,
    AuditEvent.RUN_CANCELLED: AuditCategory.DATA_MODIFICATION,
    AuditEvent.RUN_COMPLETED: AuditCategory.SYSTEM,
    AuditEvent.RUN_FAILED: AuditCategory.SYSTEM,

    AuditEvent.PROJECT_CREATED: AuditCategory.DATA_MODIFICATION,
    AuditEvent.PROJECT_DELETED: AuditCategory.DATA_MODIFICATION,
    AuditEvent.PROJECT_UPDATED: AuditCategory.DATA_MODIFICATION,

    AuditEvent.DATA_EXPORTED: AuditCategory.DATA_ACCESS,
    AuditEvent.REPORT_GENERATED: AuditCategory.DATA_ACCESS,
    AuditEvent.SOURCES_ACCESSED: AuditCategory.DATA_ACCESS,

    AuditEvent.CONFIG_CHANGED: AuditCategory.ADMINISTRATIVE,
    AuditEvent.USER_CREATED: AuditCategory.ADMINISTRATIVE,
    AuditEvent.USER_DELETED: AuditCategory.ADMINISTRATIVE,
    AuditEvent.PERMISSIONS_CHANGED: AuditCategory.ADMINISTRATIVE,

    AuditEvent.RATE_LIMIT_EXCEEDED: AuditCategory.SECURITY,
    AuditEvent.SUSPICIOUS_ACTIVITY: AuditCategory.SECURITY,
    AuditEvent.SSRF_BLOCKED: AuditCategory.SECURITY,
    AuditEvent.VALIDATION_FAILED: AuditCategory.SECURITY,
}


@dataclass
class AuditRecord:
    """Structured audit log record."""
    timestamp: str
    event: str
    category: str
    user_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action_result: str  # "success" or "failure"
    client_ip: Optional[str]
    user_agent: Optional[str]
    details: Dict[str, Any]
    correlation_id: Optional[str]

    def to_json(self) -> str:
        """Convert to JSON string for logging."""
        return json.dumps(asdict(self), default=str)


# ============= Core Logging Functions =============

async def audit_log(
    event: AuditEvent,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """
    Log an audit event.

    Args:
        event: The type of event
        user_id: ID of the user performing the action
        resource_type: Type of resource affected (e.g., "run", "project")
        resource_id: ID of the affected resource
        success: Whether the action succeeded
        details: Additional event-specific details
        request: FastAPI request object for extracting client info
        correlation_id: Request/trace correlation ID
    """
    # Extract client info from request
    client_ip = None
    user_agent = None
    if request:
        client_ip = _get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:200]

    # Build audit record
    record = AuditRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        event=event.value,
        category=EVENT_CATEGORIES.get(event, AuditCategory.SYSTEM).value,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action_result="success" if success else "failure",
        client_ip=client_ip,
        user_agent=user_agent,
        details=_sanitize_details(details or {}),
        correlation_id=correlation_id,
    )

    # Log the record
    audit_logger.info(record.to_json())

    # Also store in database for querying (async, fire-and-forget)
    if os.getenv("AUDIT_STORE_DB", "false").lower() == "true":
        asyncio.create_task(_store_audit_record(record))


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (set by reverse proxies)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return "unknown"


def _sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize details dict to remove sensitive information.

    Removes or masks:
    - Passwords
    - API keys
    - Tokens
    - Credit card numbers
    - SSNs
    """
    sensitive_keys = {
        "password", "secret", "token", "api_key", "apikey",
        "authorization", "auth", "credential", "credit_card",
        "ssn", "social_security"
    }

    sanitized = {}
    for key, value in details.items():
        key_lower = key.lower()

        # Check if key contains sensitive terms
        if any(s in key_lower for s in sensitive_keys):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_details(value)
        elif isinstance(value, str) and len(value) > 1000:
            # Truncate very long strings
            sanitized[key] = value[:1000] + "...[truncated]"
        else:
            sanitized[key] = value

    return sanitized


async def _store_audit_record(record: AuditRecord) -> None:
    """Store audit record in database for querying."""
    try:
        from models.db import db
        await db().auditLogs.insert_one(asdict(record))
    except Exception as e:
        # Don't let audit storage failures affect the main operation
        logging.getLogger(__name__).warning(f"Failed to store audit record: {e}")


# ============= Decorator for Easy Auditing =============

def audit_action(
    event: AuditEvent,
    resource_type: Optional[str] = None,
    get_resource_id: Optional[Callable] = None,
    get_user_id: Optional[Callable] = None,
):
    """
    Decorator to automatically audit function calls.

    Args:
        event: The audit event type
        resource_type: Type of resource being affected
        get_resource_id: Function to extract resource ID from args/kwargs
        get_user_id: Function to extract user ID from args/kwargs

    Example:
        @audit_action(
            event=AuditEvent.PROJECT_DELETED,
            resource_type="project",
            get_resource_id=lambda args, kwargs: kwargs.get("project_id"),
            get_user_id=lambda args, kwargs: kwargs.get("user").sub
        )
        async def delete_project(project_id: str, user: User):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract IDs
            resource_id = None
            user_id = None

            if get_resource_id:
                try:
                    resource_id = get_resource_id(args, kwargs)
                except Exception:
                    pass

            if get_user_id:
                try:
                    user_id = get_user_id(args, kwargs)
                except Exception:
                    pass

            # Try to get request from kwargs
            request = kwargs.get("request")

            try:
                result = await func(*args, **kwargs)

                # Log success
                await audit_log(
                    event=event,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    success=True,
                    request=request,
                )

                return result

            except Exception as e:
                # Log failure
                await audit_log(
                    event=event,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    success=False,
                    details={"error": str(e), "error_type": type(e).__name__},
                    request=request,
                )
                raise

        return wrapper
    return decorator


# ============= Convenience Functions =============

async def log_auth_success(
    user_id: str,
    auth_method: str,
    request: Optional[Request] = None,
) -> None:
    """Log a successful authentication."""
    await audit_log(
        event=AuditEvent.AUTH_LOGIN_SUCCESS,
        user_id=user_id,
        details={"auth_method": auth_method},
        request=request,
    )


async def log_auth_failure(
    reason: str,
    attempted_user: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    """Log a failed authentication attempt."""
    await audit_log(
        event=AuditEvent.AUTH_LOGIN_FAILURE,
        user_id=attempted_user,
        success=False,
        details={"reason": reason},
        request=request,
    )


async def log_run_created(
    user_id: str,
    run_id: str,
    project_id: str,
    mode: str,
    request: Optional[Request] = None,
) -> None:
    """Log run creation."""
    await audit_log(
        event=AuditEvent.RUN_CREATED,
        user_id=user_id,
        resource_type="run",
        resource_id=run_id,
        details={"project_id": project_id, "mode": mode},
        request=request,
    )


async def log_run_deleted(
    user_id: str,
    run_id: str,
    request: Optional[Request] = None,
) -> None:
    """Log run deletion."""
    await audit_log(
        event=AuditEvent.RUN_DELETED,
        user_id=user_id,
        resource_type="run",
        resource_id=run_id,
        request=request,
    )


async def log_security_event(
    event: AuditEvent,
    details: Dict[str, Any],
    user_id: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    """Log a security-related event."""
    await audit_log(
        event=event,
        user_id=user_id,
        success=False,
        details=details,
        request=request,
    )
