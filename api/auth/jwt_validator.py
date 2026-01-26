"""
JWT validation with support for RS256 (JWKS) and HS256.

Features:
- JWKS caching with auto-refresh
- Configurable issuer/audience validation
- Support for both access tokens and API keys
"""

import os
import time
import logging
import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import httpx
import jwt
from jwt import PyJWKClient, PyJWK
from jwt.exceptions import (
    InvalidTokenError as JWTInvalidTokenError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    DecodeError
)

from .exceptions import InvalidTokenError, ExpiredTokenError, AuthenticationError

logger = logging.getLogger(__name__)


@dataclass
class JWTConfig:
    """JWT validation configuration."""

    # JWT settings
    secret_key: Optional[str] = None  # For HS256
    jwks_url: Optional[str] = None     # For RS256 with JWKS
    algorithm: str = "RS256"

    # Validation settings
    issuer: Optional[str] = None
    audience: Optional[str] = None

    # Cache settings
    jwks_cache_ttl: int = 3600  # 1 hour

    # Demo mode (for development)
    demo_mode: bool = False
    demo_user_id: str = "demo-user"

    @classmethod
    def from_env(cls) -> "JWTConfig":
        """Load configuration from environment variables."""
        return cls(
            secret_key=os.getenv("JWT_SECRET_KEY"),
            jwks_url=os.getenv("JWT_JWKS_URL"),
            algorithm=os.getenv("JWT_ALGORITHM", "RS256"),
            issuer=os.getenv("JWT_ISSUER"),
            audience=os.getenv("JWT_AUDIENCE"),
            jwks_cache_ttl=int(os.getenv("JWT_JWKS_CACHE_TTL", "3600")),
            demo_mode=os.getenv("AUTH_DEMO_MODE", "false").lower() == "true",
            demo_user_id=os.getenv("AUTH_DEMO_USER_ID", "demo-user")
        )


class JWTValidator:
    """
    JWT token validator with JWKS support.

    Usage:
        validator = JWTValidator(JWTConfig.from_env())
        user_info = await validator.validate_token(token)
    """

    def __init__(self, config: JWTConfig):
        self.config = config
        self._jwks_client: Optional[PyJWKClient] = None
        self._jwks_cache_time: float = 0
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of JWKS client."""
        if self._initialized:
            return

        if self.config.jwks_url:
            try:
                self._jwks_client = PyJWKClient(
                    self.config.jwks_url,
                    cache_keys=True,
                    lifespan=self.config.jwks_cache_ttl
                )
                logger.info(f"JWKS client initialized for: {self.config.jwks_url}")
            except Exception as e:
                logger.error(f"Failed to initialize JWKS client: {e}")
                raise AuthenticationError(f"Failed to initialize authentication: {e}")

        self._initialized = True

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token and return the decoded payload.

        Args:
            token: The JWT token string (without "Bearer " prefix)

        Returns:
            Dict containing user info from token payload

        Raises:
            InvalidTokenError: If token is malformed or signature fails
            ExpiredTokenError: If token has expired
            AuthenticationError: For other auth failures
        """
        # Demo mode - return fake user for development
        if self.config.demo_mode:
            logger.debug("Auth in demo mode - returning demo user")
            return {
                "sub": self.config.demo_user_id,
                "email": f"{self.config.demo_user_id}@demo.local",
                "demo": True
            }

        # Check if auth is properly configured
        if not self.config.secret_key and not self.config.jwks_url:
            logger.warning("No JWT secret or JWKS URL configured - falling back to demo mode")
            return {
                "sub": self.config.demo_user_id,
                "email": f"{self.config.demo_user_id}@demo.local",
                "demo": True,
                "warning": "auth_not_configured"
            }

        self._ensure_initialized()

        try:
            # Get signing key
            if self.config.algorithm.startswith("RS"):
                # RS256/RS384/RS512 - use JWKS
                if not self._jwks_client:
                    raise AuthenticationError("JWKS client not configured for RS algorithm")
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                key = signing_key.key
            else:
                # HS256/HS384/HS512 - use secret key
                if not self.config.secret_key:
                    raise AuthenticationError("Secret key not configured for HS algorithm")
                key = self.config.secret_key

            # Build decode options
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "sub"]
            }

            # Decode and validate
            payload = jwt.decode(
                token,
                key,
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer,
                options=options
            )

            logger.debug(f"Token validated for user: {payload.get('sub')}")
            return payload

        except ExpiredSignatureError:
            raise ExpiredTokenError("Token has expired")
        except InvalidAudienceError:
            raise InvalidTokenError("Invalid token audience")
        except InvalidIssuerError:
            raise InvalidTokenError("Invalid token issuer")
        except DecodeError as e:
            raise InvalidTokenError(f"Failed to decode token: {str(e)}")
        except JWTInvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error validating token: {e}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    def validate_api_key(self, api_key: str) -> Dict[str, Any]:
        """
        Validate an API key.

        For now, this is a placeholder that could be extended to:
        - Look up API keys in database
        - Validate against a secret
        - Check rate limits per key

        Args:
            api_key: The API key to validate

        Returns:
            Dict containing user/service info for this API key
        """
        # TODO: Implement proper API key validation against database
        # For now, check against a configured master API key
        master_key = os.getenv("API_MASTER_KEY")

        if master_key and api_key == master_key:
            return {
                "sub": "api-service",
                "type": "api_key",
                "scope": "full"
            }

        # In demo mode, accept any API key
        if self.config.demo_mode:
            return {
                "sub": f"api-{hashlib.sha256(api_key.encode()).hexdigest()[:8]}",
                "type": "api_key",
                "demo": True
            }

        raise InvalidTokenError("Invalid API key")


# Global validator instance (lazy initialized)
_validator: Optional[JWTValidator] = None


def get_jwt_validator() -> JWTValidator:
    """Get or create the global JWT validator."""
    global _validator
    if _validator is None:
        config = JWTConfig.from_env()
        _validator = JWTValidator(config)

        # Log configuration (without secrets)
        logger.info(f"JWT validator configured: algorithm={config.algorithm}, "
                   f"issuer={config.issuer}, audience={config.audience}, "
                   f"demo_mode={config.demo_mode}")
    return _validator
