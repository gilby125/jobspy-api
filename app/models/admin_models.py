from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class SearchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledSearchRequest(BaseModel):
    name: str = Field(..., description="Name for this search")
    search_term: Optional[str] = Field(None, description="Job search term")
    location: Optional[str] = Field(None, description="Job location")
    site_names: List[str] = Field(default=["indeed", "linkedin"], description="Job sites to search")
    country_indeed: str = Field(default="USA", description="Country for Indeed searches")
    results_wanted: int = Field(default=50, description="Number of results per site")
    job_type: Optional[str] = Field(None, description="Job type filter")
    is_remote: Optional[bool] = Field(None, description="Remote job filter")
    schedule_time: Optional[datetime] = Field(None, description="When to run the search (null for immediate)")
    recurring: bool = Field(default=False, description="Whether this is a recurring search")
    recurring_interval: Optional[str] = Field(None, description="Interval for recurring searches (daily, weekly, monthly)")


class ScheduledSearchResponse(BaseModel):
    id: str
    name: str
    status: SearchStatus
    search_params: Dict[str, Any]
    created_at: datetime
    scheduled_time: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    jobs_found: Optional[int]
    error_message: Optional[str]
    recurring: bool
    recurring_interval: Optional[str]
    next_run: Optional[datetime]


class AdminStats(BaseModel):
    total_searches: int
    searches_today: int
    total_jobs_found: int
    jobs_found_today: int
    active_searches: int
    failed_searches_today: int
    cache_hit_rate: float
    system_health: Dict[str, Any]


class BulkSearchRequest(BaseModel):
    searches: List[ScheduledSearchRequest] = Field(..., description="List of searches to schedule")
    batch_name: Optional[str] = Field(None, description="Name for this batch of searches")


class SearchTemplate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    search_params: Dict[str, Any] = Field(..., description="Default search parameters")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SystemConfig(BaseModel):
    max_concurrent_searches: int = Field(default=5, description="Maximum concurrent searches")
    default_rate_limit: int = Field(default=100, description="Default rate limit per hour")
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_expiry: int = Field(default=3600, description="Cache expiry in seconds")
    alert_email: Optional[str] = Field(None, description="Email for system alerts")
    maintenance_mode: bool = Field(default=False, description="Enable maintenance mode")


class AdminUser(BaseModel):
    username: str
    role: str  # admin, operator, viewer
    permissions: List[str]
    last_login: Optional[datetime]
    created_at: datetime


class SearchLog(BaseModel):
    id: str
    search_id: str
    level: str  # INFO, WARNING, ERROR
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]]