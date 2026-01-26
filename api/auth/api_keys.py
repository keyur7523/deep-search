"""
API Key management with support for rotation.

Features:
- Multiple active API keys (for rotation)
- Key expiration dates
- Graceful rotation with overlap period
- Key usage tracking
- Rate limiting per key

Usage:
    from auth.api_keys import validate_api_key, APIKeyInfo

    key_info = await validate_api_key(request_api_key)
    if key_info:
        # Key is valid
        user_id = key_info.user_id
"""

import os
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class KeyStatus(Enum):
    """Status of an API key."""
    ACTIVE = "active"
    ROTATING = "rotating"  # Old key during rotation period
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class APIKeyInfo:
    """Information about a validated API key."""
    key_id: str
    user_id: str
    name: str
    status: KeyStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    scopes: List[str] = field(default_factory=list)
    rate_limit: Optional[int] = None  # Requests per minute, None = default
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============= Key Storage =============

# In-memory key storage for demo/development
# In production, use database storage with encryption
_api_keys: Dict[str, APIKeyInfo] = {}

# Load keys from environment
def _load_env_keys():
    """
    Load API keys from environment variables.

    Format: API_KEY_<NAME>=<key>:<user_id>:<expires_days>
    Example: API_KEY_ADMIN=sk-abc123:user_admin:365
             API_KEY_SERVICE=sk-xyz789:service_account:0 (0 = never expires)
    """
    global _api_keys

    for key, value in os.environ.items():
        if key.startswith("API_KEY_") and value:
            try:
                name = key[8:]  # Remove "API_KEY_" prefix
                parts = value.split(":")

                if len(parts) >= 2:
                    api_key = parts[0]
                    user_id = parts[1]
                    expires_days = int(parts[2]) if len(parts) > 2 else 0

                    # Hash the key for storage
                    key_hash = _hash_key(api_key)

                    expires_at = None
                    if expires_days > 0:
                        expires_at = datetime.utcnow() + timedelta(days=expires_days)

                    _api_keys[key_hash] = APIKeyInfo(
                        key_id=f"env_{name.lower()}",
                        user_id=user_id,
                        name=name,
                        status=KeyStatus.ACTIVE,
                        created_at=datetime.utcnow(),
                        expires_at=expires_at,
                        scopes=["*"],  # Full access for env keys
                    )
                    logger.info(f"Loaded API key from environment: {name}")
            except Exception as e:
                logger.warning(f"Failed to parse API key {key}: {e}")

    # Also load the legacy single API key format
    legacy_key = os.getenv("API_SECRET_KEY")
    if legacy_key:
        key_hash = _hash_key(legacy_key)
        if key_hash not in _api_keys:
            _api_keys[key_hash] = APIKeyInfo(
                key_id="legacy_default",
                user_id="default_user",
                name="Legacy Default Key",
                status=KeyStatus.ACTIVE,
                created_at=datetime.utcnow(),
                scopes=["*"],
            )
            logger.info("Loaded legacy API key from API_SECRET_KEY")


def _hash_key(key: str) -> str:
    """
    Create a secure hash of an API key.

    Uses SHA-256 with a salt for storage comparison.
    """
    salt = os.getenv("API_KEY_SALT", "deep-search-default-salt")
    return hashlib.sha256(f"{salt}:{key}".encode()).hexdigest()


# ============= Validation =============

async def validate_api_key(key: str) -> Optional[APIKeyInfo]:
    """
    Validate an API key and return its info if valid.

    Args:
        key: The raw API key from the request

    Returns:
        APIKeyInfo if key is valid, None otherwise
    """
    if not key:
        return None

    # Ensure keys are loaded
    if not _api_keys:
        _load_env_keys()

    # Hash the provided key for comparison
    key_hash = _hash_key(key)

    # Look up the key
    key_info = _api_keys.get(key_hash)
    if not key_info:
        logger.debug("API key not found")
        return None

    # Check status
    if key_info.status == KeyStatus.REVOKED:
        logger.warning(f"Revoked API key used: {key_info.key_id}")
        return None

    if key_info.status == KeyStatus.EXPIRED:
        logger.warning(f"Expired API key used: {key_info.key_id}")
        return None

    # Check expiration
    if key_info.expires_at and datetime.utcnow() > key_info.expires_at:
        key_info.status = KeyStatus.EXPIRED
        logger.warning(f"API key expired: {key_info.key_id}")
        return None

    # Update last used timestamp
    key_info.last_used_at = datetime.utcnow()

    # Log rotating key usage
    if key_info.status == KeyStatus.ROTATING:
        logger.info(f"Rotating (old) API key used: {key_info.key_id}")

    return key_info


def has_scope(key_info: APIKeyInfo, required_scope: str) -> bool:
    """
    Check if a key has the required scope.

    Args:
        key_info: The validated API key info
        required_scope: The scope to check (e.g., "runs:create", "admin:read")

    Returns:
        True if the key has the scope
    """
    if not key_info.scopes:
        return False

    # Wildcard scope grants everything
    if "*" in key_info.scopes:
        return True

    # Check exact match
    if required_scope in key_info.scopes:
        return True

    # Check prefix match (e.g., "runs:*" matches "runs:create")
    scope_parts = required_scope.split(":")
    if len(scope_parts) > 1:
        prefix_scope = f"{scope_parts[0]}:*"
        if prefix_scope in key_info.scopes:
            return True

    return False


# ============= Key Rotation =============

async def rotate_key(
    old_key: str,
    new_key: str,
    overlap_hours: int = 24
) -> Optional[str]:
    """
    Rotate an API key with an overlap period.

    During the overlap period, both keys will work.
    After the overlap period, the old key will be marked as expired.

    Args:
        old_key: The current API key to rotate
        new_key: The new API key
        overlap_hours: Hours to keep old key active (default 24)

    Returns:
        The new key ID if successful, None if old key not found
    """
    if not _api_keys:
        _load_env_keys()

    old_hash = _hash_key(old_key)
    old_info = _api_keys.get(old_hash)

    if not old_info:
        logger.warning("Attempted to rotate non-existent key")
        return None

    # Mark old key as rotating with expiration
    old_info.status = KeyStatus.ROTATING
    old_info.expires_at = datetime.utcnow() + timedelta(hours=overlap_hours)

    # Create new key with same permissions
    new_hash = _hash_key(new_key)
    new_key_id = f"{old_info.key_id}_rotated_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    _api_keys[new_hash] = APIKeyInfo(
        key_id=new_key_id,
        user_id=old_info.user_id,
        name=f"{old_info.name} (Rotated)",
        status=KeyStatus.ACTIVE,
        created_at=datetime.utcnow(),
        expires_at=old_info.expires_at if old_info.expires_at else None,
        scopes=old_info.scopes.copy(),
        rate_limit=old_info.rate_limit,
        metadata=old_info.metadata.copy(),
    )

    logger.info(f"API key rotated: {old_info.key_id} -> {new_key_id}")
    logger.info(f"Old key will expire in {overlap_hours} hours")

    return new_key_id


async def revoke_key(key: str, reason: str = "Manual revocation") -> bool:
    """
    Immediately revoke an API key.

    Args:
        key: The API key to revoke
        reason: Reason for revocation (for audit log)

    Returns:
        True if key was revoked, False if not found
    """
    if not _api_keys:
        _load_env_keys()

    key_hash = _hash_key(key)
    key_info = _api_keys.get(key_hash)

    if not key_info:
        return False

    key_info.status = KeyStatus.REVOKED
    key_info.metadata["revoked_at"] = datetime.utcnow().isoformat()
    key_info.metadata["revoked_reason"] = reason

    logger.warning(f"API key revoked: {key_info.key_id} - {reason}")
    return True


# ============= Key Generation =============

def generate_api_key(prefix: str = "sk") -> str:
    """
    Generate a new secure API key.

    Format: {prefix}_{random_bytes}
    Example: sk_a1b2c3d4e5f6g7h8

    Args:
        prefix: Key prefix (default "sk" for secret key)

    Returns:
        A new random API key
    """
    import secrets
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


async def create_key(
    user_id: str,
    name: str,
    scopes: Optional[List[str]] = None,
    expires_days: Optional[int] = None,
    rate_limit: Optional[int] = None,
) -> tuple[str, APIKeyInfo]:
    """
    Create a new API key for a user.

    Args:
        user_id: The user ID to associate with the key
        name: A friendly name for the key
        scopes: Permission scopes (default ["*"])
        expires_days: Days until expiration (None = never)
        rate_limit: Custom rate limit (requests/minute)

    Returns:
        Tuple of (raw_key, key_info)
    """
    raw_key = generate_api_key()
    key_hash = _hash_key(raw_key)
    key_id = f"key_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets_token_hex(4)}"

    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

    key_info = APIKeyInfo(
        key_id=key_id,
        user_id=user_id,
        name=name,
        status=KeyStatus.ACTIVE,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
        scopes=scopes or ["*"],
        rate_limit=rate_limit,
    )

    _api_keys[key_hash] = key_info

    logger.info(f"Created new API key: {key_id} for user {user_id}")

    # Return raw key (only time it's available) and info
    return raw_key, key_info


def secrets_token_hex(n: int) -> str:
    """Generate n random hex bytes."""
    import secrets
    return secrets.token_hex(n)


# ============= Initialization =============

# Load keys on module import
_load_env_keys()
