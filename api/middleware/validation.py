"""
Input validation and sanitization middleware.

Provides comprehensive input validation to prevent:
- XSS attacks via malicious topic strings
- NoSQL injection via crafted config values
- Resource exhaustion via oversized inputs
- Invalid data that could break downstream processing

Usage:
    from middleware.validation import (
        sanitize_topic,
        validate_config,
        ValidationError
    )

    topic = sanitize_topic(user_input)
    config = validate_config(raw_config)
"""

import re
import logging
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, field_validator, model_validator
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ValidationError(HTTPException):
    """Exception raised when input validation fails."""

    def __init__(self, field: str, message: str, value: Any = None):
        detail = {
            "error": "validation_error",
            "field": field,
            "message": message
        }
        if value is not None and len(str(value)) < 100:
            detail["received"] = str(value)[:100]
        super().__init__(status_code=422, detail=detail)


# ============= Constants =============

# Maximum lengths for various inputs
MAX_TOPIC_LENGTH = 500
MAX_GOAL_LENGTH = 2000
MAX_CONFIG_STRING_LENGTH = 200
MAX_URL_LENGTH = 2048

# Allowed config keys (whitelist approach)
ALLOWED_CONFIG_KEYS: Set[str] = {
    "forceMode",
    "deepMode",
    "minCitations",
    "requireRecent",
    "maxParagraphs",
    "rounds",
    "resultsPerRound",
    "keepPerParagraph",
    "searchProvider",
    "academicOnly",
    "excludeDomains",
    "includeDomains",
    "dateRange",
    "language",
}

# Valid values for enum-like configs
VALID_FORCE_MODES = {"simple", "agentic", None}
VALID_SEARCH_PROVIDERS = {"hybrid", "academic", "web", "semantic_scholar", "arxiv"}
VALID_LANGUAGES = {"en", "es", "fr", "de", "zh", "ja", "ko", "pt", "ru", "ar"}

# Patterns that might indicate injection attempts
SUSPICIOUS_PATTERNS = [
    r'\$\w+',           # MongoDB operators like $gt, $where
    r'\{\s*\$',         # JSON with MongoDB operators
    r'javascript:',     # JavaScript protocol
    r'<script',         # Script tags
    r'on\w+\s*=',       # Event handlers like onclick=
    r'eval\s*\(',       # eval() calls
    r'expression\s*\(', # CSS expression()
]

COMPILED_SUSPICIOUS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


# ============= Sanitization Functions =============

def sanitize_string(value: str, max_length: int, field_name: str) -> str:
    """
    Sanitize a string input.

    - Strips whitespace
    - Enforces max length
    - Removes null bytes
    - Checks for suspicious patterns
    """
    if not isinstance(value, str):
        raise ValidationError(field_name, "Must be a string", type(value).__name__)

    # Remove null bytes (can cause issues in C-based libraries)
    value = value.replace('\x00', '')

    # Strip and normalize whitespace
    value = ' '.join(value.split())

    # Check length
    if len(value) > max_length:
        raise ValidationError(
            field_name,
            f"Exceeds maximum length of {max_length} characters",
            f"{len(value)} chars"
        )

    # Check for suspicious patterns
    for pattern in COMPILED_SUSPICIOUS:
        if pattern.search(value):
            logger.warning(f"Suspicious pattern detected in {field_name}: {pattern.pattern}")
            raise ValidationError(
                field_name,
                "Contains invalid characters or patterns"
            )

    return value


def sanitize_topic(topic: str) -> str:
    """
    Sanitize a research topic string.

    Args:
        topic: Raw topic string from user input

    Returns:
        Sanitized topic string

    Raises:
        ValidationError: If topic is invalid
    """
    if not topic:
        raise ValidationError("topic", "Topic cannot be empty")

    topic = sanitize_string(topic, MAX_TOPIC_LENGTH, "topic")

    # Topic should have at least some meaningful content
    if len(topic) < 3:
        raise ValidationError("topic", "Topic must be at least 3 characters")

    # Check for topics that are just URLs (should use URL field instead)
    url_pattern = re.compile(r'^https?://\S+$', re.IGNORECASE)
    if url_pattern.match(topic):
        raise ValidationError(
            "topic",
            "Topic should be a research question, not a URL"
        )

    return topic


def sanitize_goal(goal: str) -> str:
    """
    Sanitize a project goal/description string.

    Args:
        goal: Raw goal string from user input

    Returns:
        Sanitized goal string
    """
    if not goal:
        return ""  # Goal is optional

    return sanitize_string(goal, MAX_GOAL_LENGTH, "goal")


def sanitize_url(url: str, field_name: str = "url") -> str:
    """
    Sanitize and validate a URL.

    Args:
        url: Raw URL string
        field_name: Name of the field for error messages

    Returns:
        Sanitized URL string

    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError(field_name, "URL cannot be empty")

    url = url.strip()

    if len(url) > MAX_URL_LENGTH:
        raise ValidationError(field_name, f"URL exceeds maximum length of {MAX_URL_LENGTH}")

    # Must start with http:// or https://
    if not re.match(r'^https?://', url, re.IGNORECASE):
        raise ValidationError(field_name, "URL must start with http:// or https://")

    # Check for suspicious patterns in URL
    for pattern in COMPILED_SUSPICIOUS:
        if pattern.search(url):
            raise ValidationError(field_name, "URL contains invalid characters")

    return url


# ============= Config Validation =============

def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize a configuration dictionary.

    Args:
        config: Raw config dictionary from user input

    Returns:
        Validated and sanitized config dictionary

    Raises:
        ValidationError: If config contains invalid values
    """
    if not isinstance(config, dict):
        raise ValidationError("config", "Config must be a dictionary", type(config).__name__)

    validated = {}

    for key, value in config.items():
        # Check for unknown keys (whitelist approach)
        if key not in ALLOWED_CONFIG_KEYS:
            logger.warning(f"Unknown config key ignored: {key}")
            continue

        # Validate specific keys
        try:
            validated[key] = _validate_config_value(key, value)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(key, f"Invalid value: {str(e)}")

    return validated


def _validate_config_value(key: str, value: Any) -> Any:
    """Validate a single config value based on its key."""

    # Handle None values
    if value is None:
        return None

    # String enums
    if key == "forceMode":
        if value not in VALID_FORCE_MODES:
            raise ValidationError(key, f"Must be one of: {VALID_FORCE_MODES}", value)
        return value

    if key == "searchProvider":
        if value not in VALID_SEARCH_PROVIDERS:
            raise ValidationError(key, f"Must be one of: {VALID_SEARCH_PROVIDERS}", value)
        return value

    if key == "language":
        if value not in VALID_LANGUAGES:
            raise ValidationError(key, f"Must be one of: {VALID_LANGUAGES}", value)
        return value

    # Boolean values
    if key in {"deepMode", "requireRecent", "academicOnly"}:
        if not isinstance(value, bool):
            raise ValidationError(key, "Must be a boolean", value)
        return value

    # Integer values with ranges
    if key == "minCitations":
        return _validate_int_range(key, value, 0, 100)

    if key == "maxParagraphs":
        return _validate_int_range(key, value, 1, 20)

    if key == "rounds":
        return _validate_int_range(key, value, 1, 5)

    if key == "resultsPerRound":
        return _validate_int_range(key, value, 1, 20)

    if key == "keepPerParagraph":
        return _validate_int_range(key, value, 1, 20)

    # Domain lists
    if key in {"excludeDomains", "includeDomains"}:
        return _validate_domain_list(key, value)

    # Date range
    if key == "dateRange":
        return _validate_date_range(value)

    # Unknown key that passed whitelist - return as-is with string sanitization
    if isinstance(value, str):
        return sanitize_string(value, MAX_CONFIG_STRING_LENGTH, key)

    return value


def _validate_int_range(key: str, value: Any, min_val: int, max_val: int) -> int:
    """Validate an integer value is within range."""
    if not isinstance(value, (int, float)):
        raise ValidationError(key, f"Must be a number between {min_val} and {max_val}", value)

    value = int(value)
    if value < min_val or value > max_val:
        raise ValidationError(key, f"Must be between {min_val} and {max_val}", value)

    return value


def _validate_domain_list(key: str, value: Any) -> List[str]:
    """Validate a list of domain names."""
    if not isinstance(value, list):
        raise ValidationError(key, "Must be a list of domain names", type(value).__name__)

    if len(value) > 20:
        raise ValidationError(key, "Maximum 20 domains allowed", len(value))

    validated = []
    domain_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$')

    for domain in value:
        if not isinstance(domain, str):
            raise ValidationError(key, "Domain must be a string", domain)

        domain = domain.strip().lower()
        if len(domain) > 253:
            raise ValidationError(key, "Domain name too long", domain)

        if not domain_pattern.match(domain):
            raise ValidationError(key, f"Invalid domain format: {domain}")

        validated.append(domain)

    return validated


def _validate_date_range(value: Any) -> Dict[str, str]:
    """Validate a date range object."""
    if not isinstance(value, dict):
        raise ValidationError("dateRange", "Must be an object with 'from' and/or 'to' keys")

    validated = {}
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

    for date_key in ["from", "to"]:
        if date_key in value:
            date_val = value[date_key]
            if not isinstance(date_val, str):
                raise ValidationError(f"dateRange.{date_key}", "Must be a date string (YYYY-MM-DD)")

            if not date_pattern.match(date_val):
                raise ValidationError(f"dateRange.{date_key}", "Must be in YYYY-MM-DD format", date_val)

            validated[date_key] = date_val

    return validated


# ============= Pydantic Models with Validation =============

class ValidatedNewProject(BaseModel):
    """Validated project creation request."""
    title: str = Field(..., min_length=3, max_length=MAX_TOPIC_LENGTH)
    goal: str = Field(default="", max_length=MAX_GOAL_LENGTH)
    maxParagraphs: int = Field(default=6, ge=1, le=20)

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        return sanitize_topic(v)

    @field_validator('goal')
    @classmethod
    def validate_goal(cls, v: str) -> str:
        return sanitize_goal(v)


class ValidatedCreateRunRequest(BaseModel):
    """Validated run creation request."""
    projectId: str = Field(..., min_length=24, max_length=24)
    config: Dict[str, Any] = Field(default_factory=dict)
    idempotencyKey: Optional[str] = Field(
        default=None,
        min_length=16,
        max_length=64
    )

    @field_validator('projectId')
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        # MongoDB ObjectId is 24 hex characters
        if not re.match(r'^[a-fA-F0-9]{24}$', v):
            raise ValueError("Invalid project ID format")
        return v

    @field_validator('config')
    @classmethod
    def validate_config_field(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        return validate_config(v)

    @field_validator('idempotencyKey')
    @classmethod
    def validate_idempotency_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Only allow alphanumeric, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Idempotency key can only contain alphanumeric characters, hyphens, and underscores")
        return v
