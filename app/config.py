"""Configuration settings for the JobSpy Docker API."""
import os
from typing import List, Optional, Any, Dict, Tuple
import logging

# Try to load .env files - will be ignored if python-dotenv is not installed
try:
    from dotenv import load_dotenv, find_dotenv
    # Load only .env by default
    dotenv_file = find_dotenv(".env")
    if dotenv_file:
        load_dotenv(dotenv_file)
    
    # .env.local is not loaded by default anymore
    # If you need to load it, do so explicitly in your code
except ImportError:
    pass

logger = logging.getLogger(__name__)

class Settings:
    """Simple settings class that loads values from environment variables."""
    
    def __init__(self):
        # Track the source of each setting
        self.setting_sources = {}
        
        # API Security
        self.API_KEYS, self.API_KEYS_SOURCE = self._get_setting_with_source(
            "API_KEYS", "", self._parse_list
        )
        self.API_KEY_HEADER_NAME, self.API_KEY_HEADER_NAME_SOURCE = self._get_setting_with_source(
            "API_KEY_HEADER_NAME", "x-api-key"
        )
        self.ENABLE_API_KEY_AUTH, self.ENABLE_API_KEY_AUTH_SOURCE = self._get_setting_with_source(
            "ENABLE_API_KEY_AUTH", "false", self._parse_bool
        )
        
        # Rate Limiting
        self.RATE_LIMIT_ENABLED, self.RATE_LIMIT_ENABLED_SOURCE = self._get_setting_with_source(
            "RATE_LIMIT_ENABLED", "false", self._parse_bool
        )
        self.RATE_LIMIT_REQUESTS, self.RATE_LIMIT_REQUESTS_SOURCE = self._get_setting_with_source(
            "RATE_LIMIT_REQUESTS", "100", int
        )
        self.RATE_LIMIT_TIMEFRAME, self.RATE_LIMIT_TIMEFRAME_SOURCE = self._get_setting_with_source(
            "RATE_LIMIT_TIMEFRAME", "3600", int
        )
        
        # Proxy Configuration
        self.DEFAULT_PROXIES, self.DEFAULT_PROXIES_SOURCE = self._get_setting_with_source(
            "DEFAULT_PROXIES", "", self._parse_list
        )
        self.CA_CERT_PATH, self.CA_CERT_PATH_SOURCE = self._get_setting_with_source(
            "CA_CERT_PATH", None
        )
        
        # JobSpy Default Settings
        default_sites = "indeed,linkedin,zip_recruiter,glassdoor,google,bayt,naukri"
        self.DEFAULT_SITE_NAMES, self.DEFAULT_SITE_NAMES_SOURCE = self._get_setting_with_source(
            "DEFAULT_SITE_NAMES", default_sites, self._parse_list
        )
        self.DEFAULT_RESULTS_WANTED, self.DEFAULT_RESULTS_WANTED_SOURCE = self._get_setting_with_source(
            "DEFAULT_RESULTS_WANTED", "20", int
        )
        self.DEFAULT_DISTANCE, self.DEFAULT_DISTANCE_SOURCE = self._get_setting_with_source(
            "DEFAULT_DISTANCE", "50", int
        )
        self.DEFAULT_DESCRIPTION_FORMAT, self.DEFAULT_DESCRIPTION_FORMAT_SOURCE = self._get_setting_with_source(
            "DEFAULT_DESCRIPTION_FORMAT", "markdown"
        )
        self.DEFAULT_COUNTRY_INDEED, self.DEFAULT_COUNTRY_INDEED_SOURCE = self._get_setting_with_source(
            "DEFAULT_COUNTRY_INDEED", None
        )
        
        # Database Configuration
        self.DATABASE_URL, self.DATABASE_URL_SOURCE = self._get_setting_with_source(
            "DATABASE_URL", None
        )
        
        # Cache and Queue Configuration
        self.REDIS_URL, self.REDIS_URL_SOURCE = self._get_setting_with_source(
            "REDIS_URL", None
        )
        self.CACHE_BACKEND, self.CACHE_BACKEND_SOURCE = self._get_setting_with_source(
            "CACHE_BACKEND", "redis"
        )
        
        # Celery Configuration
        self.CELERY_BROKER_URL, self.CELERY_BROKER_URL_SOURCE = self._get_setting_with_source(
            "CELERY_BROKER_URL", None
        )
        self.CELERY_RESULT_BACKEND, self.CELERY_RESULT_BACKEND_SOURCE = self._get_setting_with_source(
            "CELERY_RESULT_BACKEND", None
        )
        
        # Caching
        self.ENABLE_CACHE, self.ENABLE_CACHE_SOURCE = self._get_setting_with_source(
            "ENABLE_CACHE", "true", self._parse_bool
        )
        self.CACHE_EXPIRY, self.CACHE_EXPIRY_SOURCE = self._get_setting_with_source(
            "CACHE_EXPIRY", "3600", int
        )
        
        # Worker Configuration
        self.SCRAPING_FREQUENCY_HOURS, self.SCRAPING_FREQUENCY_HOURS_SOURCE = self._get_setting_with_source(
            "SCRAPING_FREQUENCY_HOURS", "24", int
        )
        self.WORKER_CONCURRENCY, self.WORKER_CONCURRENCY_SOURCE = self._get_setting_with_source(
            "WORKER_CONCURRENCY", "2", int
        )
        self.RETRY_MAX_ATTEMPTS, self.RETRY_MAX_ATTEMPTS_SOURCE = self._get_setting_with_source(
            "RETRY_MAX_ATTEMPTS", "3", int
        )
        self.RETRY_DELAY_SECONDS, self.RETRY_DELAY_SECONDS_SOURCE = self._get_setting_with_source(
            "RETRY_DELAY_SECONDS", "300", int
        )
        
        # Job Tracking Configuration
        self.JOB_DEDUPLICATION_ENABLED, self.JOB_DEDUPLICATION_ENABLED_SOURCE = self._get_setting_with_source(
            "JOB_DEDUPLICATION_ENABLED", "true", self._parse_bool
        )
        self.JOB_EXPIRY_DAYS, self.JOB_EXPIRY_DAYS_SOURCE = self._get_setting_with_source(
            "JOB_EXPIRY_DAYS", "30", int
        )
        self.ENABLE_WEBHOOKS, self.ENABLE_WEBHOOKS_SOURCE = self._get_setting_with_source(
            "ENABLE_WEBHOOKS", "true", self._parse_bool
        )
        
        # Logging
        self.LOG_LEVEL, self.LOG_LEVEL_SOURCE = self._get_setting_with_source(
            "LOG_LEVEL", "INFO"
        )
        self.ENVIRONMENT, self.ENVIRONMENT_SOURCE = self._get_setting_with_source(
            "ENVIRONMENT", "production"
        )
        
        # CORS
        self.CORS_ORIGINS, self.CORS_ORIGINS_SOURCE = self._get_setting_with_source(
            "CORS_ORIGINS", "*", self._parse_list
        )
        
        # Health Endpoints
        self.ENABLE_HEALTH_ENDPOINTS, self.ENABLE_HEALTH_ENDPOINTS_SOURCE = self._get_setting_with_source(
            "ENABLE_HEALTH_ENDPOINTS", "true", self._parse_bool
        )
        self.ENABLE_DETAILED_HEALTH, self.ENABLE_DETAILED_HEALTH_SOURCE = self._get_setting_with_source(
            "ENABLE_DETAILED_HEALTH", "true", self._parse_bool
        )
        
        # API Documentation
        self.ENABLE_SWAGGER_UI, self.ENABLE_SWAGGER_UI_SOURCE = self._get_setting_with_source(
            "ENABLE_SWAGGER_UI", "true", self._parse_bool
        )
        self.ENABLE_REDOC, self.ENABLE_REDOC_SOURCE = self._get_setting_with_source(
            "ENABLE_REDOC", "true", self._parse_bool
        )
        self.SWAGGER_UI_PATH, self.SWAGGER_UI_PATH_SOURCE = self._get_setting_with_source(
            "SWAGGER_UI_PATH", "/docs"
        )
        self.REDOC_PATH, self.REDOC_PATH_SOURCE = self._get_setting_with_source(
            "REDOC_PATH", "/redoc"
        )
        
        # Fix configuration inconsistencies
        self._fix_configuration_inconsistencies()
    
    def _get_setting_with_source(self, key: str, default_value: Any, 
                                parser_func=None) -> Tuple[Any, str]:
        """Get a setting value and its source."""
        if key in os.environ:
            value = os.environ[key]
            source = f"environment variable ({value})"
        else:
            value = default_value
            source = f"default value ({value})"
        
        # Apply parser if provided
        if parser_func and value is not None:
            value = parser_func(value)
            
        # Log loading for critical settings
        critical_settings = ["ENABLE_API_KEY_AUTH", "API_KEYS", "RATE_LIMIT_ENABLED", "ENABLE_CACHE"]
        if key in critical_settings:
            logger.debug(f"Setting {key}={value} loaded from {source}")
            
        return value, source
        
    def _fix_configuration_inconsistencies(self):
        """Fix any inconsistencies in configuration."""
        # If API keys are configured but auth is disabled, log a warning
        if self.API_KEYS and not self.ENABLE_API_KEY_AUTH:
            logger.warning("API keys are configured but authentication is disabled. This may lead to security issues.")
    
    def _parse_bool(self, value: Any) -> bool:
        """Parse a boolean from a string or any value."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("yes", "true", "t", "1", "on")
        return bool(value)
    
    def _parse_list(self, value: Any) -> List[str]:
        """Parse a comma-separated list from a string."""
        if not value:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return []
    
    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings with their sources, useful for debugging."""
        settings_with_sources = {}
        for key in dir(self):
            if key.isupper() and not key.endswith("_SOURCE"):
                source_attr = f"{key}_SOURCE"
                source = getattr(self, source_attr) if hasattr(self, source_attr) else "unknown"
                settings_with_sources[key] = {
                    "value": getattr(self, key),
                    "source": source
                }
        return settings_with_sources

# Create a global settings instance
settings = Settings()
