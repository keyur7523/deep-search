"""
Authentication-related exceptions.
"""

from typing import Optional, Dict, Any


class AuthenticationError(Exception):
    """Base authentication error."""

    def __init__(
        self,
        message: str,
        code: str = "AUTH_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class InvalidTokenError(AuthenticationError):
    """Token is malformed or signature verification failed."""

    def __init__(self, message: str = "Invalid token", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "INVALID_TOKEN", details)


class ExpiredTokenError(AuthenticationError):
    """Token has expired."""

    def __init__(self, message: str = "Token has expired", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "TOKEN_EXPIRED", details)


class InsufficientPermissionsError(AuthenticationError):
    """User lacks required permissions."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        required_scope: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if required_scope:
            details["required_scope"] = required_scope
        super().__init__(message, "INSUFFICIENT_PERMISSIONS", details)


class APIKeyError(AuthenticationError):
    """Invalid or missing API key."""

    def __init__(self, message: str = "Invalid API key", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "INVALID_API_KEY", details)
