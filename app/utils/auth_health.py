"""Utility functions for checking authentication health."""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def check_auth_configuration() -> Dict[str, Any]:
    """
    Check the authentication configuration and return status details.
    This helps diagnose authentication issues by checking all relevant settings.
    """
    # Import here to avoid circular imports
    from app.core.config import settings
    
    # Check settings  
    auth_enabled = settings.ENABLE_API_KEY_AUTH
    keys_configured = bool(settings.api_keys_list)
    keys_count = len(settings.api_keys_list)
    
    # Check for configuration inconsistencies
    inconsistent_config = (keys_configured and not auth_enabled)
    
    # Generate recommendations
    recommendations = []
    if inconsistent_config:
        recommendations.append(
            "API keys are configured but authentication is disabled. Consider enabling ENABLE_API_KEY_AUTH."
        )
        logger.warning("API keys are configured but authentication is disabled. This may lead to unexpected behavior.")
    
    # Determine if authentication is needed
    auth_required = auth_enabled and keys_configured
    
    return {
        "auth_required": auth_required,
        "settings": {
            "auth_enabled": auth_enabled,
            "api_keys_configured": keys_configured,
            "api_keys_count": keys_count,
            "header_name": settings.API_KEY_HEADER_NAME,
        },
        "inconsistent_config": inconsistent_config,
        "recommendations": recommendations
    }
