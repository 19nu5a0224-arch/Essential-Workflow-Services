"""
Cache Utility Module for Dashboard API using Cashews with Tag-Based Invalidation.

Implements multi-level caching with request-level and shared cache layers,
predictable keys for targeted invalidation, and tag-based deletion support.
"""

from contextvars import ContextVar
from typing import Any, Callable, List, Optional, TypeVar

from cashews import cache

from app.core.config import settings
from app.core.logging import logger

# Type variable for generic function return
T = TypeVar("T")

# Request-level cache (fastest, request-scoped)
request_cache: ContextVar[dict] = ContextVar("request_cache", default={})


class MultiLevelCacheManager:
    """Multi-level cache manager with request-level and shared caching using Cashews."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        """Initialize the shared cache backend with application settings."""
        if self._initialized:
            return

        try:
            logger.info(f"Initializing cache with backend: {settings.CACHE_BACKEND}")

            if settings.CACHE_BACKEND == "redis":
                cache.setup(
                    f"redis://{settings.CACHE_ENDPOINT}",
                    client_side=True,
                )
            elif settings.CACHE_BACKEND == "memcached":
                cache.setup(
                    f"memcached://{settings.CACHE_ENDPOINT}",
                    client_side=True,
                )
            else:  # memory backend
                cache.setup("mem://", client_side=True, size=1000)

            self._initialized = True
            logger.info("Cache initialized successfully with Cashews")

        except Exception as e:
            logger.error(f"Failed to initialize cache: {str(e)}")
            self._initialized = False
            raise

    # Request-level cache methods (fastest)
    def get_request_cache(self, key: str) -> Optional[Any]:
        """Get value from request-scoped cache."""
        cache_dict = request_cache.get()
        return cache_dict.get(key)

    def set_request_cache(self, key: str, value: Any) -> None:
        """Set value in request-scoped cache."""
        cache_dict = request_cache.get()
        cache_dict[key] = value

    def delete_request_cache(self, key: str) -> bool:
        """Delete value from request-scoped cache."""
        cache_dict = request_cache.get()
        if key in cache_dict:
            del cache_dict[key]
            return True
        return False

    # Shared cache methods using Cashews with tags
    async def get_shared(self, key: str) -> Optional[Any]:
        """Get value from shared cache."""
        if not self._initialized:
            return None

        try:
            value = await cache.get(key)
            if value is not None:
                logger.debug(f"Shared cache hit for key: {key}")
            return value
        except Exception as e:
            logger.error(f"Error getting shared cache key {key}: {str(e)}")
            return None

    async def set_shared(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Set value in shared cache with optional tags."""
        if not self._initialized:
            return False

        try:
            final_ttl = ttl or settings.CACHE_TTL_DEFAULT

            # Set with tags for efficient invalidation
            if tags:
                await cache.set(key, value, expire=final_ttl, tags=tags)
                logger.debug(
                    f"Shared cache set for key: {key} with TTL: {final_ttl}s and tags: {tags}"
                )
            else:
                await cache.set(key, value, expire=final_ttl)
                logger.debug(f"Shared cache set for key: {key} with TTL: {final_ttl}s")

            return True
        except Exception as e:
            logger.error(f"Error setting shared cache key {key}: {str(e)}")
            return False

    async def delete_shared(self, key: str) -> bool:
        """Delete value from shared cache."""
        if not self._initialized:
            return False

        try:
            await cache.delete(key)
            logger.debug(f"Shared cache deleted for key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting shared cache key {key}: {str(e)}")
            return False

    async def delete_by_tags(self, *tags: str) -> bool:
        """
        Delete all cache entries with any of the specified tags.
        This is THE way to do pattern invalidation with Memcached.

        Example:
            await cache_manager.delete_by_tags("dashboard", "user:123")
        """
        if not self._initialized:
            return False

        try:
            for tag in tags:
                await cache.delete_tags(tag)
                # logger.info(f"Deleted cache entries with tag: {tag}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache by tags {tags}: {str(e)}")
            return False

    # Multi-level operations
    async def get_multi_level(self, key: str) -> Optional[Any]:
        """Get value from cache hierarchy (request-scoped → shared)."""
        # Try request-scoped cache first
        request_value = self.get_request_cache(key)
        if request_value is not None:
            logger.debug(f"Request cache hit for key: {key}")
            return request_value

        # Try shared cache layer
        shared_value = await self.get_shared(key)
        if shared_value is not None:
            # Populate request-scoped cache for subsequent calls
            self.set_request_cache(key, shared_value)
            return shared_value

        logger.debug(f"Cache miss for key: {key}")
        return None

    async def set_multi_level(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Set value in both cache layers with tags."""
        # Set in request-scoped cache (immediate)
        self.set_request_cache(key, value)

        # Set in shared cache layer (async) with tags
        shared_success = await self.set_shared(key, value, ttl, tags)

        return shared_success

    async def delete_multi_level(self, key: str) -> bool:
        """Delete value from both cache layers."""
        # Delete from both layers
        request_success = self.delete_request_cache(key)
        shared_success = await self.delete_shared(key)

        return request_success or shared_success

    async def delete_multi_level_by_tags(self, *tags: str) -> bool:
        """Delete values with specified tags from both cache layers."""
        # Clear request cache when invalidating by tags
        request_cache.set({})
        logger.debug("Request cache cleared due to tag-based invalidation")

        # Delete from shared cache using tags
        shared_success = await self.delete_by_tags(*tags)

        return shared_success

    async def clear_request_cache(self):
        """Clear the request-scoped cache."""
        request_cache.set({})
        logger.debug("Request cache cleared")

    async def clear_shared_cache(self) -> bool:
        """Clear all values from shared cache."""
        if not self._initialized:
            return False

        try:
            await cache.clear()
            logger.info("Shared cache cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing shared cache: {str(e)}")
            return False

    async def close(self):
        """Close cache connections."""
        await cache.close()
        self._initialized = False


def generate_predictable_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate predictable cache key for easy invalidation.

    Examples:
    - comments:dashboard:123
    - dashboard:user:456
    """
    parts = [prefix]

    # Add arguments as key components
    for arg in args:
        if arg is not None:
            parts.append(str(arg))

    # Add keyword arguments (ignore common parameters)
    ignore_params = ["session", "current_user", "user_info", "self"]
    for key, value in sorted(kwargs.items()):
        if key not in ignore_params and value is not None:
            parts.append(f"{key}={str(value)}")

    return ":".join(parts)


def extract_tags_from_args(prefix: str, func_name: str, *args, **kwargs) -> List[str]:
    """Extract meaningful tags from function arguments for cache invalidation."""
    tags = [f"resource:{prefix}"]

    # Extract entity-specific tags
    entity_keys = {
        "dashboard_id": "dashboard",
        "user_id": "user",
        "comment_id": "comment",
        "entity_id": "entity",
        "workflow_id": "workflow",
        "share_id": "share",
        "schedule_id": "schedule",
        "integration_id": "integration",
    }

    # Add specific entity tags
    for key, entity_type in entity_keys.items():
        if key in kwargs and kwargs[key] is not None:
            tags.append(f"entity:{entity_type}:{kwargs[key]}")

    # Add operation-specific tags based on function name
    if "all" in func_name or "list" in func_name:
        tags.append(f"collection:{prefix}")

        # Add user-specific collection tags
        if "user_id" in kwargs and kwargs["user_id"] is not None:
            tags.append(f"collection:{prefix}:user:{kwargs['user_id']}")
        elif (
            "user_info" in kwargs
            and kwargs["user_info"]
            and "id" in kwargs["user_info"]
        ):
            tags.append(f"collection:{prefix}:user:{kwargs['user_info']['id']}")

    elif "by_id" in func_name or "get_" in func_name:
        # Add entity-specific detail tags
        for key, entity_type in entity_keys.items():
            if key in kwargs and kwargs[key] is not None:
                tags.append(f"detail:{entity_type}:{kwargs[key]}")

    # Add relationship tags for combined entities
    if "dashboard_id" in kwargs and kwargs["dashboard_id"] is not None:
        if "user_id" in kwargs and kwargs["user_id"] is not None:
            tags.append(
                f"relationship:dashboard:{kwargs['dashboard_id']}:user:{kwargs['user_id']}"
            )
        elif (
            "user_info" in kwargs
            and kwargs["user_info"]
            and "id" in kwargs["user_info"]
        ):
            tags.append(
                f"relationship:dashboard:{kwargs['dashboard_id']}:user:{kwargs['user_info']['id']}"
            )

    return list(set(tags))  # Remove duplicates


def cached_with_prefix(
    prefix: str,
    ttl: Optional[int] = None,
    use_request_cache: bool = True,
):
    """
    Caching decorator with prefix-based keys and tag support for efficient invalidation.

    Args:
        prefix: Key prefix for cache key generation
        ttl: Time to live in seconds
        use_request_cache: Whether to use request-level caching
    """

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Get cache manager instance
            cache_manager = MultiLevelCacheManager()
            if not cache_manager._initialized:
                await cache_manager.initialize()

            # Generate prefix-based cache key
            cache_key = generate_predictable_key(prefix, *args, **kwargs)

            # Generate tags for invalidation
            tags = extract_tags_from_args(prefix, func.__name__, *args, **kwargs)

            # Try to get from cache
            if use_request_cache:
                cached_result = await cache_manager.get_multi_level(cache_key)
            else:
                cached_result = await cache_manager.get_shared(cache_key)

            if cached_result is not None:
                logger.info(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_result

            # Cache miss - execute function
            logger.info(f"Cache miss for {func.__name__}: {cache_key}")
            result = await func(*args, **kwargs)

            # Use consistent TTL configuration
            final_ttl = ttl or settings.CACHE_TTL_DEFAULT

            # Cache the result if it's not None
            if result is not None:
                if use_request_cache:
                    await cache_manager.set_multi_level(
                        cache_key, result, ttl=final_ttl, tags=tags
                    )
                else:
                    await cache_manager.set_shared(
                        cache_key, result, ttl=final_ttl, tags=tags
                    )

            return result

        return async_wrapper

    return decorator


# Specialized decorators using consistent TTL configuration with tag support
def cached_dashboard(ttl: Optional[int] = None):
    """Caching decorator for dashboard operations."""
    return cached_with_prefix(
        prefix="dashboard",
        ttl=ttl or settings.CACHE_TTL_DASHBOARD,
        use_request_cache=False,
    )


def cached_comments(ttl: Optional[int] = None):
    """Caching decorator for comment operations."""
    return cached_with_prefix(
        prefix="comments",
        ttl=ttl or settings.CACHE_TTL_DEFAULT,
        use_request_cache=False,
    )


def cached_features(ttl: Optional[int] = None):
    """Caching decorator for features operations."""
    return cached_with_prefix(
        prefix="features",
        ttl=ttl or settings.CACHE_TTL_DEFAULT,
        use_request_cache=False,
    )


def cached_n8n_workflows(ttl: Optional[int] = None):
    """Caching decorator for n8n workflow operations."""
    return cached_with_prefix(
        prefix="n8n",
        ttl=ttl or settings.CACHE_TTL_DEFAULT,
        use_request_cache=False,
    )


def cached_shares(ttl: Optional[int] = None):
    """Caching decorator specifically for share operations."""
    return cached_with_prefix(
        prefix="shares",
        ttl=ttl or settings.CACHE_TTL_DEFAULT,
        use_request_cache=False,
    )


def cached_schedules(ttl: Optional[int] = None):
    """Caching decorator specifically for schedule operations."""
    return cached_with_prefix(
        prefix="schedules",
        ttl=ttl or settings.CACHE_TTL_DEFAULT,
        use_request_cache=False,
    )


# Global cache instance
_cache_manager = MultiLevelCacheManager()


async def get_cache() -> MultiLevelCacheManager:
    """Get the global cache manager instance."""
    if not _cache_manager._initialized:
        await _cache_manager.initialize()
    return _cache_manager


async def initialize_cache() -> MultiLevelCacheManager:
    """Initialize cache with application settings."""
    await _cache_manager.initialize()
    return _cache_manager


async def clear_request_cache():
    """Clear the request-scoped cache."""
    await _cache_manager.clear_request_cache()


async def invalidate_cache_by_tags(*tags: str):
    """
    Invalidate cache entries by tags.

    Examples:
        # Invalidate all dashboard caches
        await invalidate_cache_by_tags("resource:dashboard")

        # Invalidate specific dashboard
        await invalidate_cache_by_tags("entity:dashboard:123")

        # Invalidate dashboard list for user
        await invalidate_cache_by_tags("collection:dashboard:user:456")

        # Invalidate multiple tags
        await invalidate_cache_by_tags("resource:dashboard", "entity:dashboard:123")
    """
    cache_manager = await get_cache()
    return await cache_manager.delete_multi_level_by_tags(*tags)
