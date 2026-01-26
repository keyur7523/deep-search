"""
FastAPI dependencies for authentication.

Usage:
    @app.get("/protected")
    async def protected_route(user: User = Depends(get_current_user)):
        return {"user_id": user.sub}
"""

import os
import logging
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from pydantic import BaseModel

from .jwt_validator import get_jwt_validator, JWTConfig
from .exceptions import (
    AuthenticationError,
    InvalidTokenError,
    ExpiredTokenError,
    InsufficientPermissionsError
)
from .api_keys import validate_api_key as validate_api_key_v2, APIKeyInfo, KeyStatus

logger = logging.getLogger(__name__)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class User(BaseModel):
    """Authenticated user model."""
    sub: str  # User ID (subject)
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    demo: bool = False  # True if using demo/dev authentication
    scopes: list[str] = []

    @property
    def user_id(self) -> str:
        """Alias for sub (user ID)."""
        return self.sub


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header)
) -> User:
    """
    Get the current authenticated user from JWT or API key.

    Tries authentication in order:
    1. Bearer token (JWT)
    2. X-API-Key header
    3. Falls back to demo mode if enabled

    Raises:
        HTTPException(401): If authentication fails
    """
    validator = get_jwt_validator()

    # Try Bearer token first
    if credentials and credentials.credentials:
        try:
            payload = await validator.validate_token(credentials.credentials)
            return User(
                sub=payload.get("sub", "unknown"),
                email=payload.get("email"),
                name=payload.get("name"),
                picture=payload.get("picture"),
                demo=payload.get("demo", False),
                scopes=payload.get("scope", "").split() if payload.get("scope") else []
            )
        except ExpiredTokenError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except InvalidTokenError as e:
            raise HTTPException(
                status_code=401,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"}
            )
        except AuthenticationError as e:
            raise HTTPException(
                status_code=401,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"}
            )

    # Try API key with new rotation-aware validation
    if api_key:
        try:
            # First try new API key system with rotation support
            key_info = await validate_api_key_v2(api_key)
            if key_info:
                # Log if using a rotating (old) key
                if key_info.status == KeyStatus.ROTATING:
                    logger.info(f"Request using rotating API key: {key_info.key_id} - "
                               f"expires at {key_info.expires_at}")

                return User(
                    sub=key_info.user_id,
                    name=key_info.name,
                    demo=False,
                    scopes=key_info.scopes
                )

            # Fall back to legacy JWT validator for old keys
            payload = validator.validate_api_key(api_key)
            return User(
                sub=payload.get("sub", "api-user"),
                demo=payload.get("demo", False),
                scopes=payload.get("scope", "").split() if payload.get("scope") else ["api"]
            )
        except InvalidTokenError as e:
            raise HTTPException(
                status_code=401,
                detail=str(e),
                headers={"WWW-Authenticate": "ApiKey"}
            )

    # Check if demo mode is enabled (development only)
    config = JWTConfig.from_env()
    if config.demo_mode:
        # Log warning in production-like environments
        if os.getenv("RENDER") or os.getenv("PRODUCTION"):
            logger.warning("Using demo authentication in production-like environment!")

        return User(
            sub=config.demo_user_id,
            email=f"{config.demo_user_id}@demo.local",
            demo=True
        )

    # Check if auth is configured at all
    if not config.secret_key and not config.jwks_url:
        logger.warning("No authentication configured - using demo mode. "
                      "Set JWT_SECRET_KEY or JWT_JWKS_URL for production.")
        return User(
            sub=config.demo_user_id,
            email=f"{config.demo_user_id}@demo.local",
            demo=True
        )

    # No valid authentication provided
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header)
) -> Optional[User]:
    """
    Get the current user if authenticated, or None if not.

    Useful for endpoints that work with or without authentication,
    but may provide additional features for authenticated users.
    """
    try:
        return await get_current_user(request, credentials, api_key)
    except HTTPException:
        return None


def require_user(required_scopes: Optional[list[str]] = None):
    """
    Dependency factory for requiring specific scopes.

    Usage:
        @app.delete("/admin/users/{user_id}")
        async def delete_user(
            user_id: str,
            user: User = Depends(require_user(["admin"]))
        ):
            ...
    """
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if required_scopes:
            missing_scopes = set(required_scopes) - set(user.scopes)
            if missing_scopes and not user.demo:  # Demo users bypass scope checks
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing required scopes: {', '.join(missing_scopes)}"
                )
        return user

    return dependency


# Backward compatibility alias
get_user = get_current_user
