from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)

async def get_api_key(api_key_header: Optional[str] = Depends(api_key_header)):
    """
    Dependency that checks if the API key is valid.
    Allows requests without authentication if:
    1. API key authentication is disabled, or
    2. No API keys are configured, or
    3. API keys list is empty
    """
    # Skip authentication if it's disabled or no keys are configured
    if not settings.ENABLE_API_KEY_AUTH or not settings.api_keys_list:
        return True
    
    # At this point, auth is enabled and keys are configured, so require a key
    if not api_key_header:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, 
            detail="Missing API Key"
        )
    
    if api_key_header not in settings.api_keys_list:
        logger.warning("Invalid API key provided")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, 
            detail="Invalid API Key"
        )
    return True
