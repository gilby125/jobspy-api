from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from typing import Optional
import logging

from app.core.config import settings
from app.config import settings as app_settings

logger = logging.getLogger(__name__)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def get_api_key(request: Request, api_key: Optional[str] = Depends(api_key_header)):
    # Log detailed information about the authentication attempt
    logger.debug(f"API Key authentication check - core API_KEY configured: {bool(settings.API_KEY)}")
    logger.debug(f"Request path: {request.url.path}")
    logger.debug(f"API Key in request: {'Present' if api_key else 'Missing'}")
    
    # Check both authentication systems for consistency
    # First check app.core.config settings
    if not settings.API_KEY:
        logger.debug("No API key configured in core settings, checking app settings")
        
        # Then check app.config settings
        if not app_settings.ENABLE_API_KEY_AUTH or not app_settings.API_KEYS:
            logger.debug("Authentication disabled or no API keys configured in app settings")
            return None
        
        # App settings require auth but no core setting, issue a warning
        logger.warning("Inconsistent config: API_KEY auth enabled in app settings but not in core settings")
    
    # At this point, some form of authentication is required
    # Check if API key is missing
    if not api_key:
        logger.warning(f"API key is missing in request to {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API Key",
        )
    
    # Check against core config API key if configured
    if settings.API_KEY and api_key != settings.API_KEY:
        # Fall back to checking against app config API keys
        if not (app_settings.API_KEYS and api_key in app_settings.API_KEYS):
            logger.warning(f"Invalid API key provided in request to {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API Key",
            )
    
    logger.debug("Valid API key provided, authentication successful")
    return api_key
