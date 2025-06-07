from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

class JobSearchParams(BaseModel):
    site_name: Union[List[str], str] = Field(
        default_factory=lambda: ["indeed", "linkedin", "zip_recruiter", "glassdoor", "google", "bayt", "naukri"],
        description="Job sites to search on",
    )
    search_term: Optional[str] = Field(default=None, description="Job search term")
    google_search_term: Optional[str] = Field(default=None, description="Search term for Google jobs")
    location: Optional[str] = Field(default=None, description="Job location")
    distance: Optional[int] = Field(default=50, description="Distance in miles")
    job_type: Optional[str] = Field(default=None, description="Job type (fulltime, parttime, internship, contract)")
    proxies: Optional[List[str]] = Field(default=None, description="Proxies in format ['user:pass@host:port', 'localhost']")
    is_remote: Optional[bool] = Field(default=None, description="Remote job filter")
    results_wanted: Optional[int] = Field(default=20, description="Number of results per site")
    hours_old: Optional[int] = Field(default=None, description="Filter by hours since posting")
    easy_apply: Optional[bool] = Field(default=None, description="Filter for easy apply jobs")
    description_format: Optional[str] = Field(default="markdown", description="Format of job description")
    offset: Optional[int] = Field(default=0, description="Offset for pagination")
    verbose: Optional[int] = Field(default=2, description="Controls verbosity (0: errors only, 1: errors+warnings, 2: all logs)")
    linkedin_fetch_description: Optional[bool] = Field(default=False, description="Fetch full LinkedIn descriptions")
    linkedin_company_ids: Optional[List[int]] = Field(default=None, description="LinkedIn company IDs to filter by")
    country_indeed: Optional[str] = Field(default=None, description="Country filter for Indeed & Glassdoor")
    enforce_annual_salary: Optional[bool] = Field(default=False, description="Convert wages to annual salary")
    ca_cert: Optional[str] = Field(default=None, description="Path to CA Certificate file for proxies")

class JobResponse(BaseModel):
    count: int
    jobs: List[Dict[str, Any]]
    cached: bool = False

class PaginatedJobResponse(BaseModel):
    count: int
    total_pages: int
    current_page: int
    page_size: int
    jobs: List[Dict[str, Any]]
    cached: bool = False
    next_page: Optional[str] = None
    previous_page: Optional[str] = None

class HealthCheck(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
