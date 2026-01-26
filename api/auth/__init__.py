"""
Authentication module for Deep Search API.

Supports:
- JWT validation (RS256/HS256)
- API key authentication with rotation support
- Development/demo mode fallback
"""

from .dependencies import get_current_user, get_optional_user, require_user, User
from .jwt_validator import JWTValidator, JWTConfig
from .exceptions import (
    AuthenticationError,
    InvalidTokenError,
    ExpiredTokenError,
    InsufficientPermissionsError
)
from .api_keys import (
    validate_api_key,
    rotate_key,
    revoke_key,
    create_key,
    generate_api_key,
    APIKeyInfo,
    KeyStatus,
)

__all__ = [
    # Dependencies
    "get_current_user",
    "get_optional_user",
    "require_user",
    "User",
    # JWT
    "JWTValidator",
    "JWTConfig",
    # Exceptions
    "AuthenticationError",
    "InvalidTokenError",
    "ExpiredTokenError",
    "InsufficientPermissionsError",
    # API Keys
    "validate_api_key",
    "rotate_key",
    "revoke_key",
    "create_key",
    "generate_api_key",
    "APIKeyInfo",
    "KeyStatus",
]
