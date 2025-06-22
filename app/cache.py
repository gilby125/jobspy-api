import time
from typing import Dict, Any, Optional, Tuple
import hashlib
import json
import pandas as pd
from app.core.config import settings

class JobSearchCache:
    def __init__(self):
        self.cache: Dict[str, Tuple[float, pd.DataFrame]] = {}
        self.enabled = settings.ENABLE_CACHE
        self.expiry = settings.CACHE_EXPIRY
    
    def _generate_key(self, params: Dict[str, Any]) -> str:
        """Generate a cache key from the search parameters"""
        # Sort the dictionary to ensure consistent keys
        sorted_params = {k: params[k] for k in sorted(params.keys())}
        param_str = json.dumps(sorted_params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()
    
    async def get(self, params_or_key) -> Optional[Any]:
        """Get cached results if they exist and are not expired"""
        if not self.enabled:
            return None
        
        # Handle both dict params and string keys
        if isinstance(params_or_key, dict):
            key = self._generate_key(params_or_key)
        else:
            key = params_or_key
            
        if key not in self.cache:
            return None
            
        timestamp, data = self.cache[key]
        if time.time() - timestamp > self.expiry:
            # Cache expired
            del self.cache[key]
            return None
            
        return data
    
    async def set(self, params_or_key, data, expire: Optional[int] = None) -> None:
        """Cache search results"""
        if not self.enabled:
            return
        
        # Handle both dict params and string keys
        if isinstance(params_or_key, dict):
            key = self._generate_key(params_or_key)
        else:
            key = params_or_key
            
        expiry_time = expire or self.expiry
        self.cache[key] = (time.time(), data)
    
    def clear(self) -> None:
        """Clear all cached data"""
        self.cache.clear()
    
    def cleanup_expired(self) -> None:
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, (timestamp, _) in self.cache.items() 
            if current_time - timestamp > self.expiry
        ]
        for key in expired_keys:
            del self.cache[key]

# Initialize global cache
cache = JobSearchCache()
