from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)

async def get_api_key(request: Request, api_key: Optional[str] = Depends(api_key_header)):
    """Simple API key authentication using unified config system."""
    logger.debug(f"Request path: {request.url.path}")
    logger.debug(f"API Key in request: {'Present' if api_key else 'Missing'}")
    
    # Skip authentication if it's disabled or no keys are configured
    if not settings.ENABLE_API_KEY_AUTH or not settings.api_keys_list:
        logger.debug("Authentication disabled or no API keys configured")
        return None
    
    # At this point, authentication is required
    if not api_key:
        logger.warning(f"API key is missing in request to {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API Key",
        )
    
    # Check if API key is valid
    if api_key not in settings.api_keys_list:
        logger.warning(f"Invalid API key provided in request to {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
    
    logger.debug("Valid API key provided, authentication successful")
    return api_key
