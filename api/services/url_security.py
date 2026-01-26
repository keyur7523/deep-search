"""
URL Security module for SSRF prevention.

Validates URLs before making external requests to prevent:
- Server-Side Request Forgery (SSRF) attacks
- Access to internal network resources
- DNS rebinding attacks
- Protocol smuggling

Usage:
    from services.url_security import validate_url, URLSecurityError

    try:
        safe_url = validate_url(user_provided_url)
        # Now safe to fetch
    except URLSecurityError as e:
        # Handle invalid URL
"""

import re
import socket
import ipaddress
import logging
from typing import Optional, Set, List
from urllib.parse import urlparse
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class URLSecurityError(Exception):
    """Exception raised when URL fails security validation."""

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"URL security check failed: {reason}")


# ============= Configuration =============

@dataclass
class URLSecurityConfig:
    """Configuration for URL security checks."""

    # Allowed URL schemes
    allowed_schemes: Set[str] = None

    # If set, only these domains are allowed
    domain_whitelist: Optional[Set[str]] = None

    # Domains that are always blocked
    domain_blacklist: Set[str] = None

    # Allow redirects (can lead to SSRF if destination isn't checked)
    allow_redirects: bool = False

    # Maximum URL length
    max_url_length: int = 2048

    # Block cloud metadata endpoints
    block_cloud_metadata: bool = True

    # Resolve DNS and check IP before allowing
    check_resolved_ip: bool = True

    def __post_init__(self):
        if self.allowed_schemes is None:
            self.allowed_schemes = {"http", "https"}
        if self.domain_blacklist is None:
            self.domain_blacklist = set()


# Default configuration
DEFAULT_CONFIG = URLSecurityConfig()

# Known academic/research domains that are safe
ACADEMIC_DOMAIN_WHITELIST: Set[str] = {
    # Academic publishers
    "arxiv.org",
    "semanticscholar.org",
    "api.semanticscholar.org",
    "scholar.google.com",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "doi.org",
    "dx.doi.org",
    "sciencedirect.com",
    "springer.com",
    "link.springer.com",
    "nature.com",
    "wiley.com",
    "onlinelibrary.wiley.com",
    "ieee.org",
    "ieeexplore.ieee.org",
    "acm.org",
    "dl.acm.org",
    "jstor.org",
    "researchgate.net",
    "academia.edu",

    # Preprint servers
    "biorxiv.org",
    "medrxiv.org",
    "ssrn.com",

    # Open access
    "plos.org",
    "frontiersin.org",
    "mdpi.com",
    "hindawi.com",

    # Data APIs
    "crossref.org",
    "api.crossref.org",
    "openalex.org",
    "api.openalex.org",
    "unpaywall.org",
    "api.unpaywall.org",
}

# Cloud metadata endpoints (must be blocked to prevent SSRF)
CLOUD_METADATA_HOSTS = {
    "169.254.169.254",  # AWS, GCP, Azure metadata
    "metadata.google.internal",
    "metadata.goog",
    "169.254.170.2",  # AWS ECS task metadata
    "fd00:ec2::254",  # AWS IPv6 metadata
}

# Dangerous ports that could be used for attacks
DANGEROUS_PORTS = {22, 23, 25, 110, 143, 445, 3306, 5432, 6379, 27017}


# ============= IP Address Checks =============

def is_private_ip(ip: str) -> bool:
    """Check if an IP address is private/internal."""
    try:
        addr = ipaddress.ip_address(ip)
        return (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        )
    except ValueError:
        # Invalid IP, treat as potentially dangerous
        return True


def is_cloud_metadata_ip(ip: str) -> bool:
    """Check if IP is a cloud metadata endpoint."""
    return ip in CLOUD_METADATA_HOSTS


# ============= URL Validation =============

def validate_url(
    url: str,
    config: URLSecurityConfig = DEFAULT_CONFIG,
    purpose: str = "external_fetch"
) -> str:
    """
    Validate a URL for security before making external requests.

    Args:
        url: The URL to validate
        config: Security configuration
        purpose: Description of why URL is being fetched (for logging)

    Returns:
        The validated URL (may be normalized)

    Raises:
        URLSecurityError: If URL fails any security check
    """
    if not url:
        raise URLSecurityError(url, "URL cannot be empty")

    # Check length
    if len(url) > config.max_url_length:
        raise URLSecurityError(url, f"URL exceeds maximum length of {config.max_url_length}")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLSecurityError(url, f"Failed to parse URL: {e}")

    # Check scheme
    if parsed.scheme.lower() not in config.allowed_schemes:
        raise URLSecurityError(
            url,
            f"URL scheme '{parsed.scheme}' not allowed. Allowed: {config.allowed_schemes}"
        )

    # Check for empty host
    if not parsed.netloc:
        raise URLSecurityError(url, "URL must have a host")

    # Extract host and port
    host = parsed.hostname
    port = parsed.port

    if not host:
        raise URLSecurityError(url, "Could not extract hostname from URL")

    host_lower = host.lower()

    # Check for cloud metadata endpoints
    if config.block_cloud_metadata:
        if host_lower in CLOUD_METADATA_HOSTS:
            logger.warning(f"Blocked cloud metadata URL: {url}")
            raise URLSecurityError(url, "Access to cloud metadata endpoints is not allowed")

    # Check for localhost variants
    localhost_patterns = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
        "0177.0.0.1",  # Octal
        "2130706433",  # Decimal
        "0x7f.0x0.0x0.0x1",  # Hex
    ]

    if host_lower in localhost_patterns or host_lower.startswith("localhost."):
        logger.warning(f"Blocked localhost URL: {url}")
        raise URLSecurityError(url, "Access to localhost is not allowed")

    # Check port
    if port and port in DANGEROUS_PORTS:
        raise URLSecurityError(url, f"Port {port} is not allowed for security reasons")

    # Check blacklist
    if host_lower in config.domain_blacklist:
        raise URLSecurityError(url, f"Domain '{host_lower}' is blacklisted")

    # Check if it's a subdomain of a blacklisted domain
    for blocked in config.domain_blacklist:
        if host_lower.endswith(f".{blocked}"):
            raise URLSecurityError(url, f"Domain '{host_lower}' is blacklisted")

    # Check whitelist (if configured)
    if config.domain_whitelist:
        if not _is_domain_allowed(host_lower, config.domain_whitelist):
            raise URLSecurityError(
                url,
                f"Domain '{host_lower}' is not in the allowed list"
            )

    # Resolve DNS and check IP
    if config.check_resolved_ip:
        try:
            resolved_ips = _resolve_host(host)
            for ip in resolved_ips:
                if is_private_ip(ip):
                    logger.warning(f"URL {url} resolves to private IP {ip}")
                    raise URLSecurityError(
                        url,
                        f"URL resolves to private IP address"
                    )
                if is_cloud_metadata_ip(ip):
                    logger.warning(f"URL {url} resolves to cloud metadata IP {ip}")
                    raise URLSecurityError(
                        url,
                        "URL resolves to cloud metadata endpoint"
                    )
        except socket.gaierror:
            # DNS resolution failed - could be temporary or the domain doesn't exist
            raise URLSecurityError(url, "Failed to resolve hostname")
        except URLSecurityError:
            raise
        except Exception as e:
            logger.warning(f"Error resolving {host}: {e}")
            raise URLSecurityError(url, f"Error validating hostname: {e}")

    logger.debug(f"URL validated for {purpose}: {url}")
    return url


def _is_domain_allowed(host: str, whitelist: Set[str]) -> bool:
    """Check if a host matches any domain in the whitelist."""
    if host in whitelist:
        return True

    # Check if it's a subdomain of an allowed domain
    for allowed in whitelist:
        if host.endswith(f".{allowed}"):
            return True

    return False


def _resolve_host(host: str) -> List[str]:
    """Resolve a hostname to IP addresses."""
    try:
        # First check if it's already an IP
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass

    # Resolve hostname
    results = socket.getaddrinfo(host, None, socket.AF_UNSPEC)
    ips = list(set(result[4][0] for result in results))
    return ips


# ============= Convenience Functions =============

def validate_academic_url(url: str) -> str:
    """
    Validate a URL for academic/research purposes.

    Uses a whitelist of known academic domains.
    """
    config = URLSecurityConfig(
        domain_whitelist=ACADEMIC_DOMAIN_WHITELIST,
        check_resolved_ip=True,
        block_cloud_metadata=True,
    )
    return validate_url(url, config, purpose="academic_fetch")


def validate_web_search_url(url: str) -> str:
    """
    Validate a URL from web search results.

    More permissive than academic validation but still checks for SSRF.
    """
    # Block known problematic domains
    dangerous_domains = {
        "localhost",
        "internal",
        "intranet",
        "corp",
        "local",
    }

    config = URLSecurityConfig(
        domain_blacklist=dangerous_domains,
        check_resolved_ip=True,
        block_cloud_metadata=True,
    )
    return validate_url(url, config, purpose="web_search_result")


def is_safe_url(url: str, config: URLSecurityConfig = DEFAULT_CONFIG) -> bool:
    """
    Check if a URL is safe without raising an exception.

    Returns:
        True if URL passes all security checks, False otherwise
    """
    try:
        validate_url(url, config)
        return True
    except URLSecurityError:
        return False
    except Exception:
        return False


# ============= URL Sanitization =============

def sanitize_url_for_logging(url: str) -> str:
    """
    Sanitize a URL for safe logging (remove credentials, truncate).
    """
    try:
        parsed = urlparse(url)
        # Remove credentials
        if parsed.username or parsed.password:
            safe_netloc = parsed.hostname
            if parsed.port:
                safe_netloc = f"{safe_netloc}:{parsed.port}"
            url = parsed._replace(netloc=safe_netloc).geturl()

        # Truncate if too long
        if len(url) > 200:
            return url[:200] + "..."

        return url
    except Exception:
        return "[invalid url]"
