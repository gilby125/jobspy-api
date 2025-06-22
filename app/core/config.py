from pydantic_settings import BaseSettings
from typing import Optional, List
import os

def parse_list(value: str) -> List[str]:
    """Parse comma-separated string into list."""
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]

def parse_bool(value: str) -> bool:
    """Parse string to boolean."""
    return str(value).lower() in ('true', '1', 'yes', 'on')

class Settings(BaseSettings):
    """Unified settings class using Pydantic that replaces the custom config system."""
    
    # Project Info
    PROJECT_NAME: str = "JobSpy Docker API"
    API_V1_STR: str = "/api/v1"
    
    # Database Configuration
    DATABASE_URL: Optional[str] = None
    REDIS_URL: Optional[str] = None
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    # API Security
    API_KEYS: str = ""
    ENABLE_API_KEY_AUTH: bool = True
    API_KEY_HEADER_NAME: str = "x-api-key"
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_TIMEFRAME: int = 3600
    
    # Proxy Configuration
    DEFAULT_PROXIES: str = ""
    CA_CERT_PATH: Optional[str] = None
    
    # JobSpy Default Settings
    DEFAULT_SITE_NAMES: str = "indeed,linkedin,zip_recruiter,glassdoor,google,bayt,naukri"
    DEFAULT_RESULTS_WANTED: int = 20
    DEFAULT_DISTANCE: int = 50
    DEFAULT_DESCRIPTION_FORMAT: str = "markdown"
    DEFAULT_COUNTRY_INDEED: Optional[str] = None
    
    # Caching
    ENABLE_CACHE: bool = True
    CACHE_EXPIRY: int = 3600
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_TO_FILE: bool = True
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ENVIRONMENT: str = "development"
    
    # CORS
    CORS_ORIGINS: str = "*"
    
    # Health Endpoints
    ENABLE_HEALTH_ENDPOINTS: bool = True
    ENABLE_DETAILED_HEALTH: bool = True
    
    # API Documentation
    ENABLE_SWAGGER_UI: bool = True
    ENABLE_REDOC: bool = True
    SWAGGER_UI_PATH: str = "/docs"
    REDOC_PATH: str = "/redoc"
    
    @property
    def get_log_level(self):
        """Convert string log level to logging module level"""
        import logging
        return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)
    
    @property
    def api_keys_list(self) -> List[str]:
        """Parse API_KEYS string into list."""
        return parse_list(self.API_KEYS)
    
    @property
    def default_proxies_list(self) -> List[str]:
        """Parse DEFAULT_PROXIES string into list."""
        return parse_list(self.DEFAULT_PROXIES)
    
    @property
    def default_site_names_list(self) -> List[str]:
        """Parse DEFAULT_SITE_NAMES string into list."""
        return parse_list(self.DEFAULT_SITE_NAMES)
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return parse_list(self.CORS_ORIGINS)
    
    def get_all_settings(self) -> dict:
        """Get all settings with their sources for debugging."""
        settings_dict = {}
        
        for field_name, field_info in self.__fields__.items():
            value = getattr(self, field_name)
            env_name = field_name.upper()
            
            # Determine the source of the setting
            env_value = os.environ.get(env_name)
            if env_value is not None:
                source = "environment"
            elif hasattr(field_info, 'default') and field_info.default is not None:
                source = "default"
            else:
                source = "unset"
            
            settings_dict[field_name] = {
                "value": value,
                "source": source,
                "env_name": env_name
            }
        
        return settings_dict

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields from .env

settings = Settings()