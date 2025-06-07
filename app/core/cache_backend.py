"""
Cache backend abstraction for Redis/Valkey compatibility.
Provides a unified interface that can easily switch between Redis implementations.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Union
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    def ping(self) -> bool:
        """Test connection to cache backend."""
        pass


class RedisCompatibleBackend(CacheBackend):
    """
    Redis-compatible cache backend.
    Works with Redis, Valkey, KeyDB, and other Redis-compatible implementations.
    """
    
    def __init__(self, redis_url: Optional[str] = None, **kwargs):
        """
        Initialize Redis-compatible backend.
        
        Args:
            redis_url: Redis connection URL (redis://host:port/db)
            **kwargs: Additional Redis connection parameters
        """
        self.redis_url = redis_url or settings.REDIS_URL or "redis://localhost:6379/0"
        self.default_ttl = kwargs.get('default_ttl', settings.CACHE_EXPIRY)
        
        try:
            # Create Redis connection with connection pooling
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                **kwargs
            )
            
            # Test connection
            self.client.ping()
            logger.info(f"Connected to Redis-compatible cache at {self.redis_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis cache: {e}")
            raise
    
    def _serialize(self, value: Any) -> str:
        """Serialize value for storage."""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value)
        return json.dumps(value, default=str)
    
    def _deserialize(self, value: str) -> Any:
        """Deserialize value from storage."""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = self.client.get(key)
            if value is None:
                return None
            return self._deserialize(value)
        except Exception as e:
            logger.error(f"Cache get error for key '{key}': {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        try:
            serialized_value = self._serialize(value)
            expire_time = ttl or self.default_ttl
            
            return self.client.setex(key, expire_time, serialized_value)
        except Exception as e:
            logger.error(f"Cache set error for key '{key}': {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error for key '{key}': {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key '{key}': {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            return self.client.flushdb()
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    def ping(self) -> bool:
        """Test connection to cache backend."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Cache ping error: {e}")
            return False
    
    def get_info(self) -> dict:
        """Get cache backend information."""
        try:
            info = self.client.info()
            return {
                "backend_type": "redis_compatible",
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "keyspace": info.get("keyspace", {}),
            }
        except Exception as e:
            logger.error(f"Cache info error: {e}")
            return {"backend_type": "redis_compatible", "error": str(e)}


class InMemoryBackend(CacheBackend):
    """
    In-memory cache backend for testing and development.
    Not recommended for production use.
    """
    
    def __init__(self, **kwargs):
        """Initialize in-memory backend."""
        self.cache = {}
        self.default_ttl = kwargs.get('default_ttl', 3600)
        logger.warning("Using in-memory cache backend - not suitable for production")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return self.cache.get(key)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache (TTL ignored in memory backend)."""
        try:
            self.cache[key] = value
            return True
        except Exception as e:
            logger.error(f"Memory cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
        except Exception as e:
            logger.error(f"Memory cache delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self.cache
    
    def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            self.cache.clear()
            return True
        except Exception as e:
            logger.error(f"Memory cache clear error: {e}")
            return False
    
    def ping(self) -> bool:
        """Test connection (always available for memory backend)."""
        return True


def get_cache_backend() -> CacheBackend:
    """
    Factory function to get the appropriate cache backend.
    
    Returns:
        CacheBackend: Configured cache backend instance
    """
    cache_backend_type = getattr(settings, 'CACHE_BACKEND', 'redis').lower()
    
    if cache_backend_type == 'redis':
        return RedisCompatibleBackend()
    elif cache_backend_type == 'memory':
        return InMemoryBackend()
    else:
        logger.warning(f"Unknown cache backend '{cache_backend_type}', falling back to Redis")
        return RedisCompatibleBackend()


# Global cache instance
cache_backend = get_cache_backend()