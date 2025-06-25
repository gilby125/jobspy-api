from fastapi import APIRouter, Request, Depends, HTTPException, status
from app.pydantic_models import HealthCheck
from app.core.config import settings
import logging
import platform
import time
from app.utils.auth_health import check_auth_configuration

router = APIRouter()
logger = logging.getLogger(__name__)

# Create a dependency to check if health endpoints are enabled
async def verify_health_enabled():
    """Verify that health endpoints are enabled via configuration."""
    if not settings.ENABLE_HEALTH_ENDPOINTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health endpoints are disabled"
        )
    return True

@router.get("/health", response_model=HealthCheck, tags=["Health"], dependencies=[Depends(verify_health_enabled)])
async def health_check():
    """
    Health check endpoint to verify the API is running correctly and return system status
    """
    # Get authentication status
    auth_status = check_auth_configuration()
    
    # Build response with all the requested information
    return HealthCheck(
        status="ok",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        log_level=settings.LOG_LEVEL,
        auth={
            "enabled": settings.ENABLE_API_KEY_AUTH,
            "api_keys_configured": bool(settings.API_KEYS),
            "api_keys_count": len(settings.api_keys_list),
            "inconsistent": auth_status["inconsistent_config"],
        },
        rate_limiting={
            "enabled": settings.RATE_LIMIT_ENABLED,
            "requests_limit": settings.RATE_LIMIT_REQUESTS,
            "timeframe_seconds": settings.RATE_LIMIT_TIMEFRAME,
        },
        cache={
            "enabled": settings.ENABLE_CACHE,
            "expiry_seconds": settings.CACHE_EXPIRY,
        },
        health_endpoints={
            "enabled": settings.ENABLE_HEALTH_ENDPOINTS,
            "detailed_health": settings.ENABLE_DETAILED_HEALTH,
        },
        config={
            "default_site_names": settings.DEFAULT_SITE_NAMES,
            "default_results_wanted": settings.DEFAULT_RESULTS_WANTED,
            "default_distance": settings.DEFAULT_DISTANCE,
            "default_description_format": settings.DEFAULT_DESCRIPTION_FORMAT,
            "default_country_indeed": settings.DEFAULT_COUNTRY_INDEED,
        },
        timestamp=time.time()
    )

@router.get("/ping", tags=["Health"], dependencies=[Depends(verify_health_enabled)])
async def ping():
    """
    Simple ping endpoint for load balancers and monitoring
    """
    return {"status": "ok"}

@router.get("/auth-status", tags=["Health"], dependencies=[Depends(verify_health_enabled)])
async def auth_status(request: Request):
    """
    Diagnostic endpoint to check authentication settings
    """
    logger.info("Auth status endpoint called")
    
    # Check if the request has the API key header
    api_key_header_name = "X-API-Key"
    api_key_in_request = request.headers.get(api_key_header_name)
    
    return {
        "api_key_configured": bool(settings.api_keys_list),
        "api_key_header_name": api_key_header_name,
        "api_key_in_request": bool(api_key_in_request),
        "authentication_enabled": settings.ENABLE_API_KEY_AUTH,
        "environment": settings.ENVIRONMENT
    }

@router.get("/api-config", tags=["Health"], dependencies=[Depends(verify_health_enabled)])
async def api_config():
    """
    Diagnostic endpoint to check API configuration settings
    """
    logger.info("API configuration endpoint called")
    
    # Only provide detailed info if it's enabled
    if not settings.ENABLE_DETAILED_HEALTH:
        return {
            "status": "ok",
            "message": "Detailed health information is disabled. Enable with ENABLE_DETAILED_HEALTH=true"
        }
    
    # Build comprehensive config information
    system_info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }
    
    # Configuration information
    config = {
        "environment": settings.ENVIRONMENT,
        "log_level": settings.LOG_LEVEL,
        "authentication": {
            "enabled": settings.ENABLE_API_KEY_AUTH,
            "api_keys_configured": bool(settings.API_KEYS),
            "api_keys_count": len(settings.API_KEYS) if settings.API_KEYS else 0,
            "header_name": settings.API_KEY_HEADER_NAME,
        },
        "rate_limiting": {
            "enabled": settings.RATE_LIMIT_ENABLED,
            "requests_limit": settings.RATE_LIMIT_REQUESTS,
            "timeframe_seconds": settings.RATE_LIMIT_TIMEFRAME,
        },
        "caching": {
            "enabled": settings.ENABLE_CACHE,
            "expiry_seconds": settings.CACHE_EXPIRY,
        },
        "health_endpoints": {
            "enabled": settings.ENABLE_HEALTH_ENDPOINTS,
            "detailed_health": settings.ENABLE_DETAILED_HEALTH,
        },
    }
    
    return {
        "status": "ok",
        "system": system_info,
        "config": config,
        "timestamp": time.time()
    }

@router.get("/config-sources", tags=["Health"], dependencies=[Depends(verify_health_enabled)])
async def config_sources():
    """
    Diagnostic endpoint to view the source of each configuration setting
    """
    logger.info("Configuration sources endpoint called")
    
    # Only provide detailed info if it's enabled
    if not settings.ENABLE_DETAILED_HEALTH:
        return {
            "status": "ok",
            "message": "Detailed health information is disabled. Enable with ENABLE_DETAILED_HEALTH=true"
        }
    
    # Get all settings with their sources
    settings_with_sources = settings.get_all_settings()
    
    # Format for output, focusing on key settings
    important_settings = [
        "ENABLE_API_KEY_AUTH", "API_KEYS", "RATE_LIMIT_ENABLED", 
        "ENABLE_CACHE", "ENVIRONMENT", "LOG_LEVEL"
    ]
    
    focused_settings = {k: settings_with_sources[k] for k in important_settings if k in settings_with_sources}
    
    # Check for configuration inconsistencies
    auth_status = check_auth_configuration()
    inconsistencies = []
    
    if auth_status["inconsistent_config"]:
        inconsistencies.extend(auth_status["recommendations"])
    
    return {
        "status": "ok",
        "key_settings": focused_settings,
        "all_settings": settings_with_sources,
        "inconsistencies": inconsistencies,
        "timestamp": time.time()
    }
