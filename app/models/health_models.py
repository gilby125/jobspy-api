"""Models for health check endpoints."""
from pydantic import BaseModel
from typing import Dict, Any, Optional

class HealthCheck(BaseModel):
    """Health check response model with detailed information."""
    status: str = "ok"
    version: str = "1.0.0"
    environment: str = "production"
    log_level: str = "INFO"
    auth: Optional[Dict[str, Any]] = None
    rate_limiting: Optional[Dict[str, Any]] = None
    cache: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    health_endpoints: Optional[Dict[str, bool]] = None
    timestamp: Optional[float] = None

class DetailedHealthCheck(BaseModel):
    """Placeholder for detailed health check model."""
    status: str = "ok"
    version: str = "1.0.0"
