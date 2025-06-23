#!/usr/bin/env python3
"""
Redis connection test script.
This script tests Redis connectivity and provides debugging information.
"""
import sys
import logging
import redis
import os
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test Redis connection and provide debugging information."""
    try:
        logger.info("Testing Redis connection...")
        
        # Get Redis URL from settings
        redis_url = getattr(settings, 'REDIS_URL', None)
        if not redis_url:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        
        logger.info(f"Redis URL: {redis_url}")
        
        # Create Redis client
        redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Test basic operations
        logger.info("Testing Redis ping...")
        pong = redis_client.ping()
        logger.info(f"Redis ping response: {pong}")
        
        # Test set/get operations
        logger.info("Testing Redis set/get operations...")
        test_key = "jobspy:test:connection"
        test_value = "connection_test_successful"
        
        redis_client.set(test_key, test_value, ex=60)  # Expire in 60 seconds
        retrieved_value = redis_client.get(test_key)
        
        if retrieved_value == test_value:
            logger.info("Redis set/get test successful")
        else:
            logger.error(f"Redis set/get test failed. Expected: {test_value}, Got: {retrieved_value}")
            return False
        
        # Clean up test key
        redis_client.delete(test_key)
        
        # Get Redis info
        logger.info("Getting Redis server info...")
        info = redis_client.info()
        logger.info(f"Redis version: {info.get('redis_version', 'Unknown')}")
        logger.info(f"Connected clients: {info.get('connected_clients', 'Unknown')}")
        logger.info(f"Used memory: {info.get('used_memory_human', 'Unknown')}")
        
        logger.info("Redis connection test completed successfully!")
        return True
        
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")
        return False
    except redis.TimeoutError as e:
        logger.error(f"Redis timeout error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected Redis error: {e}")
        return False

def main():
    """Run Redis connection test."""
    try:
        logger.info("Starting Redis connection test...")
        
        if test_redis_connection():
            logger.info("Redis connection test passed!")
            return 0
        else:
            logger.error("Redis connection test failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Redis test script failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())