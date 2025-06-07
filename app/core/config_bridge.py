"""
Bridge between app.core.config and app.config to ensure consistent settings.
This module synchronizes API key settings between the two config modules.
"""
import logging

# Disabled - using unified config system
# from app.config import settings as app_settings
# from app.core.config import settings as core_settings

logger = logging.getLogger(__name__)

def sync_api_key_settings():
    """
    Synchronize API key settings between core.config and main config.
    This ensures that authentication works consistently.
    """
    # If core API_KEY is set but app API_KEYS is not, add the core key to app settings
    if core_settings.API_KEY and not app_settings.API_KEYS:
        logger.debug("Syncing core API_KEY to app API_KEYS")
        app_settings.API_KEYS = [core_settings.API_KEY]
        
    # If app has API_KEYS but core doesn't have API_KEY, set the first app key as core key
    if app_settings.API_KEYS and not core_settings.API_KEY:
        logger.debug("Setting core API_KEY from app API_KEYS")
        # We can't actually modify core_settings.API_KEY directly, but we can log a warning
        logger.warning("Cannot sync app API_KEYS to core API_KEY - core settings are immutable")
    
    # Log configuration status
    auth_enabled = bool(core_settings.API_KEY) or (app_settings.ENABLE_API_KEY_AUTH and bool(app_settings.API_KEYS))
    logger.info(f"Authentication enabled: {auth_enabled}")
    logger.debug(f"Core API_KEY configured: {bool(core_settings.API_KEY)}")
    logger.debug(f"App API_KEYS configured: {bool(app_settings.API_KEYS)}")

# Disabled - using unified config system now
# sync_api_key_settings()
