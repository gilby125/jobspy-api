import time
from collections import defaultdict
from typing import DefaultDict, List

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import settings

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.rate_limits: DefaultDict[str, List[float]] = defaultdict(list)
        self.enabled = settings.RATE_LIMIT_ENABLED
        self.max_requests = settings.RATE_LIMIT_REQUESTS
        self.timeframe = settings.RATE_LIMIT_TIMEFRAME
    
    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)
        
        # Get client identifier (use API key if available, otherwise IP)
        client_identifier = request.headers.get(settings.API_KEY_HEADER_NAME, request.client.host)
        
        # Check rate limit
        current_time = time.time()
        
        # Clean up old request timestamps
        self.rate_limits[client_identifier] = [
            timestamp for timestamp in self.rate_limits[client_identifier] 
            if current_time - timestamp < self.timeframe
        ]
        
        # Check if rate limit exceeded
        if len(self.rate_limits[client_identifier]) >= self.max_requests:
            reset_time = min(self.rate_limits[client_identifier]) + self.timeframe - current_time
            headers = {"X-RateLimit-Reset": str(int(reset_time))}
            
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.timeframe} seconds.",
                headers=headers
            )
        
        # Add current request timestamp
        self.rate_limits[client_identifier].append(current_time)
        
        # Process the request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self.max_requests - len(self.rate_limits[client_identifier])
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
