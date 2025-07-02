"""Middleware for logging requests and responses."""
import json
import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("app.middleware.request_logger")

# Paths to exclude from detailed logging
EXCLUDED_PATHS = ["/health", "/metrics"]

# Paths that should only be logged in debug mode
DEBUG_ONLY_PATHS = ["/health", "/metrics"]

# Add the missing function
async def log_request_middleware(request: Request, call_next):
    """Function-based middleware for logging requests. 
    Simpler alternative to the RequestLoggerMiddleware class."""
    # Generate a unique request ID
    request_id = request.headers.get("X-Request-ID", f"req_{time.time()}")
    
    # Get path
    path = request.url.path
    
    # Only log health checks and monitoring endpoints in debug mode
    should_log = True
    if path in DEBUG_ONLY_PATHS:
        should_log = logger.isEnabledFor(logging.DEBUG)
    
    if should_log:
        # Log the request
        client_host = request.client.host if request.client else "unknown"
        logger.info(f"Request {request_id}: {request.method} {request.url} from {client_host}")
    
    # Process the request and measure timing
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    if should_log:
        # Log the response
        logger.info(f"Response {request_id}: {response.status_code} in {process_time:.4f} seconds")
    
    # Add custom headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    
    return response

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
    async def dispatch(self, request: Request, call_next):
        # Generate a unique request ID
        request_id = request.headers.get("X-Request-ID", f"req_{time.time()}")
        
        # Get path and method
        path = request.url.path
        method = request.method  # Move method extraction here, outside the condition
        
        # Only log health checks and monitoring endpoints in debug mode
        should_log = True
        if path in DEBUG_ONLY_PATHS:
            should_log = logger.isEnabledFor(logging.DEBUG)
        
        if should_log:
            # Log the request
            client_host = request.client.host if request.client else "unknown"
            url = str(request.url)
            
            logger.info(f"Request {request_id}: {method} {url} from {client_host}")
        
        # Get body if it's a POST/PUT
        if method in ["POST", "PUT"]:
            try:
                # Store the request body for logging
                body = await request.body()
                await self._log_request_body(request_id, body)
                
                # Need to create a new Request with the body because the original was consumed
                async def new_receive():
                    return {"type": "http.request", "body": body}
                
                request = Request(
                    scope=request.scope,
                    receive=new_receive
                )
            except Exception as e:
                logger.warning(f"Failed to log request body: {str(e)}")
        
        # Process the request and measure timing
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        if should_log:
            # Log the response
            status_code = response.status_code
            logger.info(f"Response {request_id}: {status_code} in {process_time:.4f} seconds")
        
        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        return response
    
    async def _log_request_body(self, request_id: str, body: bytes):
        """Log the request body in a safe manner."""
        try:
            # Only log if body is not too large
            if len(body) > 1000:
                logger.debug(f"Request {request_id} body: [too large to log]")
                return
                
            # Try to parse as JSON
            json_body = json.loads(body)
            # Mask sensitive fields
            self._mask_sensitive_fields(json_body)
            logger.debug(f"Request {request_id} body: {json.dumps(json_body)}")
        except:
            # Not JSON, log as string (truncated if needed)
            body_str = body.decode('utf-8', errors='replace')
            if len(body_str) > 200:
                body_str = body_str[:200] + "..."
            logger.debug(f"Request {request_id} body: {body_str}")
    
    def _mask_sensitive_fields(self, data):
        """Mask sensitive fields in the request data."""
        if not isinstance(data, dict):
            return
            
        # List of fields to mask
        sensitive_fields = ["password", "token", "api_key", "secret", "credit_card"]
        
        for key in data:
            if isinstance(data[key], dict):
                self._mask_sensitive_fields(data[key])
            elif isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict):
                        self._mask_sensitive_fields(item)
            elif any(sensitive in key.lower() for sensitive in sensitive_fields):
                data[key] = "********"
    
