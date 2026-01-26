"""
HTTP Connection Pool Manager for efficient connection reuse.

Features:
- Shared connection pools per base URL
- Configurable connection limits
- Automatic cleanup on shutdown
- Thread-safe singleton pattern

Usage:
    from services.http_pool import http_pool

    # Get a client for a specific service
    client = await http_pool.get_client("https://api.semanticscholar.org")
    response = await client.get("/graph/v1/paper/search", params={...})

    # Or use the context manager for automatic cleanup
    async with http_pool.client("https://api.example.com") as client:
        response = await client.get("/endpoint")
"""

import os
import logging
import asyncio
from typing import Dict, Optional
from contextlib import asynccontextmanager
import httpx

logger = logging.getLogger(__name__)


class HTTPPoolConfig:
    """Configuration for HTTP connection pools."""

    def __init__(
        self,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        keepalive_expiry: float = 30.0,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        write_timeout: float = 30.0,
        pool_timeout: float = 10.0
    ):
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.keepalive_expiry = keepalive_expiry
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout
        self.pool_timeout = pool_timeout

    @classmethod
    def from_env(cls) -> "HTTPPoolConfig":
        """Load configuration from environment variables."""
        return cls(
            max_connections=int(os.getenv("HTTP_MAX_CONNECTIONS", "100")),
            max_keepalive_connections=int(os.getenv("HTTP_MAX_KEEPALIVE", "20")),
            keepalive_expiry=float(os.getenv("HTTP_KEEPALIVE_EXPIRY", "30.0")),
            connect_timeout=float(os.getenv("HTTP_CONNECT_TIMEOUT", "10.0")),
            read_timeout=float(os.getenv("HTTP_READ_TIMEOUT", "30.0")),
            write_timeout=float(os.getenv("HTTP_WRITE_TIMEOUT", "30.0")),
            pool_timeout=float(os.getenv("HTTP_POOL_TIMEOUT", "10.0"))
        )


class HTTPPoolManager:
    """
    Manages HTTP connection pools for different services.

    Creates and reuses httpx.AsyncClient instances per base URL,
    providing efficient connection pooling and resource management.
    """

    _instance: Optional["HTTPPoolManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        """Singleton pattern to ensure one pool manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the pool manager (only runs once due to singleton)."""
        if self._initialized:
            return

        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._config = HTTPPoolConfig.from_env()
        self._initialized = True
        logger.info(
            f"HTTPPoolManager initialized with max_connections={self._config.max_connections}, "
            f"max_keepalive={self._config.max_keepalive_connections}"
        )

    def _create_client(self, base_url: Optional[str] = None) -> httpx.AsyncClient:
        """Create a new HTTP client with configured limits."""
        limits = httpx.Limits(
            max_connections=self._config.max_connections,
            max_keepalive_connections=self._config.max_keepalive_connections,
            keepalive_expiry=self._config.keepalive_expiry
        )

        timeout = httpx.Timeout(
            connect=self._config.connect_timeout,
            read=self._config.read_timeout,
            write=self._config.write_timeout,
            pool=self._config.pool_timeout
        )

        client = httpx.AsyncClient(
            base_url=base_url,
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
            http2=True  # Enable HTTP/2 for better performance
        )

        return client

    async def get_client(self, base_url: str) -> httpx.AsyncClient:
        """
        Get or create an HTTP client for the given base URL.

        Args:
            base_url: The base URL for the client (e.g., "https://api.example.com")

        Returns:
            An httpx.AsyncClient configured for the base URL
        """
        # Normalize base URL (remove trailing slashes)
        base_url = base_url.rstrip("/")

        if base_url not in self._clients:
            async with self._lock:
                # Double-check after acquiring lock
                if base_url not in self._clients:
                    client = self._create_client(base_url)
                    self._clients[base_url] = client
                    logger.debug(f"Created HTTP client for: {base_url}")

        return self._clients[base_url]

    async def get_generic_client(self) -> httpx.AsyncClient:
        """
        Get a generic HTTP client without a base URL.

        Useful for making requests to arbitrary URLs.
        """
        key = "__generic__"
        if key not in self._clients:
            async with self._lock:
                if key not in self._clients:
                    self._clients[key] = self._create_client(None)
                    logger.debug("Created generic HTTP client")

        return self._clients[key]

    @asynccontextmanager
    async def client(self, base_url: str):
        """
        Context manager for getting an HTTP client.

        Usage:
            async with http_pool.client("https://api.example.com") as client:
                response = await client.get("/endpoint")
        """
        client = await self.get_client(base_url)
        try:
            yield client
        except Exception:
            # Log error but don't close client (it's shared)
            raise

    async def close_all(self):
        """Close all HTTP clients. Call this during application shutdown."""
        logger.info(f"Closing {len(self._clients)} HTTP clients...")
        for base_url, client in list(self._clients.items()):
            try:
                await client.aclose()
                logger.debug(f"Closed HTTP client for: {base_url}")
            except Exception as e:
                logger.error(f"Error closing HTTP client for {base_url}: {e}")

        self._clients.clear()
        logger.info("All HTTP clients closed")

    async def close_client(self, base_url: str):
        """Close a specific HTTP client."""
        base_url = base_url.rstrip("/")
        if base_url in self._clients:
            client = self._clients.pop(base_url)
            await client.aclose()
            logger.debug(f"Closed HTTP client for: {base_url}")

    def get_stats(self) -> Dict:
        """Get statistics about active connection pools."""
        return {
            "active_clients": len(self._clients),
            "clients": list(self._clients.keys()),
            "config": {
                "max_connections": self._config.max_connections,
                "max_keepalive_connections": self._config.max_keepalive_connections,
                "keepalive_expiry": self._config.keepalive_expiry
            }
        }


# Global singleton instance
http_pool = HTTPPoolManager()


# ============= Helper Functions =============

async def fetch_url(url: str, **kwargs) -> httpx.Response:
    """
    Convenience function to fetch a URL using the shared pool.

    Args:
        url: Full URL to fetch
        **kwargs: Additional arguments passed to client.get()

    Returns:
        httpx.Response object
    """
    client = await http_pool.get_generic_client()
    return await client.get(url, **kwargs)


async def post_url(url: str, **kwargs) -> httpx.Response:
    """
    Convenience function to POST to a URL using the shared pool.

    Args:
        url: Full URL to POST to
        **kwargs: Additional arguments passed to client.post()

    Returns:
        httpx.Response object
    """
    client = await http_pool.get_generic_client()
    return await client.post(url, **kwargs)


# ============= Service-Specific Clients =============

# Pre-defined base URLs for common services
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org"
ARXIV_BASE = "https://export.arxiv.org"
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov"
CROSSREF_BASE = "https://api.crossref.org"
OPENAI_BASE = "https://api.openai.com"


async def get_semantic_scholar_client() -> httpx.AsyncClient:
    """Get HTTP client for Semantic Scholar API."""
    return await http_pool.get_client(SEMANTIC_SCHOLAR_BASE)


async def get_arxiv_client() -> httpx.AsyncClient:
    """Get HTTP client for arXiv API."""
    return await http_pool.get_client(ARXIV_BASE)


async def get_pubmed_client() -> httpx.AsyncClient:
    """Get HTTP client for PubMed API."""
    return await http_pool.get_client(PUBMED_BASE)


async def get_crossref_client() -> httpx.AsyncClient:
    """Get HTTP client for CrossRef API."""
    return await http_pool.get_client(CROSSREF_BASE)


async def get_openai_client(base_url: Optional[str] = None) -> httpx.AsyncClient:
    """Get HTTP client for OpenAI API (or compatible endpoint)."""
    url = base_url or os.getenv("LLM_BASE_URL", OPENAI_BASE)
    return await http_pool.get_client(url)
