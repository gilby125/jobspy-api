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
    
    def get(self, params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """Get cached results if they exist and are not expired"""
        if not self.enabled:
            return None
            
        key = self._generate_key(params)
        if key not in self.cache:
            return None
            
        timestamp, df = self.cache[key]
        if time.time() - timestamp > self.expiry:
            # Cache expired
            del self.cache[key]
            return None
            
        return df
    
    def set(self, params: Dict[str, Any], df: pd.DataFrame) -> None:
        """Cache search results"""
        if not self.enabled:
            return
            
        key = self._generate_key(params)
        self.cache[key] = (time.time(), df)
    
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
