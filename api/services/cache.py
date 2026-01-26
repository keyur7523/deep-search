"""
In-memory caching layer for expensive operations.

Features:
- TTL-based expiration
- LRU eviction when max size reached
- Cache statistics for monitoring
- Async-safe operations
- Namespace support for different cache types

Usage:
    from services.cache import cache, cached

    # Direct cache access
    await cache.set("key", value, ttl=300)
    result = await cache.get("key")

    # Decorator for caching function results
    @cached(ttl=300, namespace="search")
    async def search_papers(query: str) -> List[Dict]:
        ...
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from functools import wraps
from collections import OrderedDict

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def ttl_remaining(self) -> float:
        return max(0, self.expires_at - time.time())


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    expirations: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "hit_rate": round(self.hit_rate, 3)
        }


class Cache:
    """
    In-memory cache with TTL and LRU eviction.

    Thread-safe for use with asyncio.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        cleanup_interval: int = 60
    ):
        """
        Args:
            max_size: Maximum number of entries before LRU eviction
            default_ttl: Default TTL in seconds
            cleanup_interval: Seconds between cleanup runs
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self._stats = CacheStats()

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.

        Args:
            key: Cache key
            default: Value to return if key not found

        Returns:
            Cached value or default
        """
        async with self._lock:
            await self._maybe_cleanup()

            entry = self._cache.get(key)
            if entry is None:
                self._stats.misses += 1
                return default

            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                self._stats.expirations += 1
                return default

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats.hits += 1

            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        ttl = ttl or self._default_ttl

        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats.evictions += 1
                logger.debug(f"Cache evicted: {oldest_key}")

            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl
            )
            self._cache.move_to_end(key)
            self._stats.sets += 1

    async def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.

        Returns:
            True if key existed and was deleted
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self, namespace: Optional[str] = None) -> int:
        """
        Clear the cache.

        Args:
            namespace: If provided, only clear keys starting with namespace

        Returns:
            Number of keys cleared
        """
        async with self._lock:
            if namespace is None:
                count = len(self._cache)
                self._cache.clear()
                return count

            keys_to_delete = [
                k for k in self._cache.keys()
                if k.startswith(f"{namespace}:")
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._cache[key]
                self._stats.expirations += 1
                return False
            return True

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get value from cache, or compute and cache it.

        Args:
            key: Cache key
            factory: Async function to compute value if not cached
            ttl: Time-to-live for new entries

        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            **self._stats.to_dict(),
            "size": len(self._cache),
            "max_size": self._max_size
        }

    async def _maybe_cleanup(self) -> None:
        """Remove expired entries if cleanup interval has passed."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        expired_keys = [
            k for k, v in self._cache.items()
            if v.is_expired
        ]

        for key in expired_keys:
            del self._cache[key]
            self._stats.expirations += 1

        if expired_keys:
            logger.debug(f"Cache cleanup: removed {len(expired_keys)} expired entries")


# Global cache instance
cache = Cache(max_size=2000, default_ttl=300)


# ============= Caching Decorator =============

def cached(
    ttl: int = 300,
    namespace: str = "default",
    key_builder: Optional[Callable[..., str]] = None
):
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds
        namespace: Cache namespace for grouping related entries
        key_builder: Custom function to build cache key from args

    Usage:
        @cached(ttl=300, namespace="search")
        async def search_papers(query: str, limit: int = 10) -> List[Dict]:
            ...

        # With custom key builder
        @cached(ttl=60, key_builder=lambda q, **kw: f"search:{q}")
        async def search(query: str, options: dict) -> List:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                key_suffix = key_builder(*args, **kwargs)
            else:
                key_suffix = _build_key_from_args(args, kwargs)

            cache_key = f"{namespace}:{func.__name__}:{key_suffix}"

            # Try to get from cache
            result = await cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return result

            # Compute and cache
            logger.debug(f"Cache miss: {cache_key}")
            result = await func(*args, **kwargs)

            if result is not None:
                await cache.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


def _build_key_from_args(args: tuple, kwargs: dict) -> str:
    """Build a cache key from function arguments."""
    # Create a deterministic string from args
    key_parts = []

    for arg in args:
        key_parts.append(_serialize_arg(arg))

    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={_serialize_arg(v)}")

    key_string = "|".join(key_parts)

    # Hash if too long
    if len(key_string) > 200:
        return hashlib.md5(key_string.encode()).hexdigest()

    return key_string


def _serialize_arg(arg: Any) -> str:
    """Serialize an argument for cache key building."""
    if isinstance(arg, (str, int, float, bool)):
        return str(arg)
    elif isinstance(arg, (list, tuple)):
        return json.dumps(arg, sort_keys=True)
    elif isinstance(arg, dict):
        return json.dumps(arg, sort_keys=True)
    else:
        return str(type(arg).__name__)


# ============= Specialized Caches =============

class SearchCache:
    """
    Specialized cache for search results.

    Features:
    - Query normalization
    - Result deduplication
    - Source-specific TTLs
    """

    def __init__(self):
        self._cache = Cache(max_size=500, default_ttl=600)  # 10 min default

    # TTLs for different sources
    TTL_SEMANTIC_SCHOLAR = 3600  # 1 hour (stable)
    TTL_ARXIV = 1800  # 30 min (updates frequently)
    TTL_WEB = 300  # 5 min (changes often)

    async def get_search_results(
        self,
        query: str,
        source: str
    ) -> Optional[list]:
        """Get cached search results."""
        key = self._build_search_key(query, source)
        return await self._cache.get(key)

    async def set_search_results(
        self,
        query: str,
        source: str,
        results: list
    ) -> None:
        """Cache search results with source-appropriate TTL."""
        key = self._build_search_key(query, source)

        ttl = {
            "semantic_scholar": self.TTL_SEMANTIC_SCHOLAR,
            "arxiv": self.TTL_ARXIV,
            "pubmed": self.TTL_SEMANTIC_SCHOLAR,
            "web": self.TTL_WEB,
        }.get(source, self.TTL_WEB)

        await self._cache.set(key, results, ttl)

    def _build_search_key(self, query: str, source: str) -> str:
        """Build normalized search key."""
        # Normalize query
        normalized = query.lower().strip()
        normalized = " ".join(normalized.split())  # Normalize whitespace

        return f"search:{source}:{hashlib.md5(normalized.encode()).hexdigest()}"

    def get_stats(self) -> Dict[str, Any]:
        return self._cache.get_stats()


class LLMCache:
    """
    Specialized cache for LLM responses.

    Features:
    - Prompt hashing
    - Temperature-aware caching (only cache low temp)
    - Token counting for stats
    """

    def __init__(self):
        self._cache = Cache(max_size=200, default_ttl=1800)  # 30 min

    async def get_response(
        self,
        messages: list,
        model: str,
        temperature: float
    ) -> Optional[str]:
        """Get cached LLM response."""
        # Don't cache high-temperature responses (they should vary)
        if temperature > 0.3:
            return None

        key = self._build_llm_key(messages, model)
        return await self._cache.get(key)

    async def set_response(
        self,
        messages: list,
        model: str,
        temperature: float,
        response: str
    ) -> None:
        """Cache LLM response."""
        if temperature > 0.3:
            return

        key = self._build_llm_key(messages, model)
        await self._cache.set(key, response)

    def _build_llm_key(self, messages: list, model: str) -> str:
        """Build cache key from messages and model."""
        content = json.dumps(messages, sort_keys=True)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"llm:{model}:{content_hash}"

    def get_stats(self) -> Dict[str, Any]:
        return self._cache.get_stats()


# Global specialized caches
search_cache = SearchCache()
llm_cache = LLMCache()


# ============= Cache Warming =============

async def warm_cache(queries: list[str]) -> int:
    """
    Pre-warm cache with common queries.

    Args:
        queries: List of queries to pre-cache

    Returns:
        Number of queries cached
    """
    from services.academic import semantic_scholar_search

    cached_count = 0
    for query in queries:
        try:
            # Check if already cached
            existing = await search_cache.get_search_results(query, "semantic_scholar")
            if existing:
                continue

            # Fetch and cache
            results = await semantic_scholar_search(query, top=10)
            if results:
                await search_cache.set_search_results(query, "semantic_scholar", results)
                cached_count += 1

        except Exception as e:
            logger.warning(f"Failed to warm cache for '{query}': {e}")

    logger.info(f"Cache warmed with {cached_count} queries")
    return cached_count
