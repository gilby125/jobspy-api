"""Sample data fixtures for testing."""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Sample job search results
SAMPLE_JOBS_DATA = [
    {
        "SITE": "indeed",
        "TITLE": "Senior Software Engineer",
        "COMPANY": "TechCorp Inc",
        "LOCATION": "San Francisco, CA",
        "JOB_TYPE": "fulltime",
        "DATE_POSTED": "2024-01-01",
        "JOB_URL": "https://indeed.com/job/123",
        "DESCRIPTION": "Build scalable web applications using Python and React.",
        "MIN_AMOUNT": 120000,
        "MAX_AMOUNT": 180000,
        "CURRENCY": "USD",
        "INTERVAL": "yearly",
        "REMOTE": False
    },
    {
        "SITE": "linkedin",
        "TITLE": "Data Scientist",
        "COMPANY": "DataCorp Ltd",
        "LOCATION": "New York, NY",
        "JOB_TYPE": "fulltime",
        "DATE_POSTED": "2024-01-02",
        "JOB_URL": "https://linkedin.com/jobs/456",
        "DESCRIPTION": "Analyze large datasets and build ML models.",
        "MIN_AMOUNT": 100000,
        "MAX_AMOUNT": 150000,
        "CURRENCY": "USD",
        "INTERVAL": "yearly",
        "REMOTE": True
    },
    {
        "SITE": "glassdoor",
        "TITLE": "Frontend Developer",
        "COMPANY": "WebDev Solutions",
        "LOCATION": "Austin, TX",
        "JOB_TYPE": "contract",
        "DATE_POSTED": "2024-01-03",
        "JOB_URL": "https://glassdoor.com/job/789",
        "DESCRIPTION": "Create responsive user interfaces with React.",
        "MIN_AMOUNT": 80000,
        "MAX_AMOUNT": 120000,
        "CURRENCY": "USD",
        "INTERVAL": "yearly",
        "REMOTE": False
    }
]

# Convert to DataFrame for JobSpy mock responses
SAMPLE_JOBS_DF = pd.DataFrame(SAMPLE_JOBS_DATA)

# Sample company data for database testing
SAMPLE_COMPANIES = [
    {
        "name": "TechCorp Inc",
        "domain": "techcorp.com",
        "industry": "Technology",
        "company_size": "51-200",
        "headquarters_location": "San Francisco, CA",
        "description": "Leading technology company"
    },
    {
        "name": "DataCorp Ltd",
        "domain": "datacorp.com",
        "industry": "Data Analytics",
        "company_size": "11-50",
        "headquarters_location": "New York, NY",
        "description": "Data analytics specialists"
    },
    {
        "name": "WebDev Solutions",
        "domain": "webdevsolutions.com",
        "industry": "Web Development",
        "company_size": "1-10",
        "headquarters_location": "Austin, TX",
        "description": "Custom web development services"
    }
]

# Sample location data
SAMPLE_LOCATIONS = [
    {
        "city": "San Francisco",
        "state": "California",
        "country": "USA",
        "region": "North America"
    },
    {
        "city": "New York",
        "state": "New York",
        "country": "USA",
        "region": "North America"
    },
    {
        "city": "Austin",
        "state": "Texas",
        "country": "USA",
        "region": "North America"
    }
]

# Sample job categories
SAMPLE_JOB_CATEGORIES = [
    {"name": "Software Development"},
    {"name": "Data Science"},
    {"name": "Frontend Development"},
    {"name": "Backend Development"},
    {"name": "DevOps"}
]

# Sample search parameters for testing
SAMPLE_SEARCH_PARAMS = {
    "basic_search": {
        "site_name": ["indeed", "linkedin"],
        "search_term": "software engineer",
        "location": "San Francisco",
        "results_wanted": 10
    },
    "advanced_search": {
        "site_name": ["indeed", "linkedin", "glassdoor"],
        "search_term": "python developer",
        "location": "San Francisco, CA",
        "job_type": "fulltime",
        "is_remote": False,
        "results_wanted": 20,
        "hours_old": 24,
        "country_indeed": "USA"
    },
    "multi_site_search": {
        "site_name": ["indeed", "linkedin", "glassdoor", "google"],
        "search_term": "data scientist",
        "location": "remote",
        "is_remote": True,
        "results_wanted": 50
    }
}

# Sample API responses for different scenarios
SAMPLE_API_RESPONSES = {
    "success_response": {
        "count": 3,
        "cached": False,
        "jobs": SAMPLE_JOBS_DATA
    },
    "cached_response": {
        "count": 3,
        "cached": True,
        "jobs": SAMPLE_JOBS_DATA
    },
    "empty_response": {
        "count": 0,
        "cached": False,
        "jobs": []
    }
}

# Sample admin data
SAMPLE_ADMIN_DATA = {
    "scheduled_searches": [
        {
            "id": "search-1",
            "name": "Daily Tech Jobs",
            "search_params": SAMPLE_SEARCH_PARAMS["basic_search"],
            "schedule": "daily",
            "status": "active"
        },
        {
            "id": "search-2",
            "name": "Weekly Data Science Jobs",
            "search_params": SAMPLE_SEARCH_PARAMS["advanced_search"],
            "schedule": "weekly",
            "status": "paused"
        }
    ],
    "analytics_data": {
        "total_jobs": 15000,
        "new_jobs_today": 250,
        "active_companies": 1200,
        "top_locations": ["San Francisco", "New York", "Austin"],
        "trending_skills": ["Python", "React", "Machine Learning"]
    }
}

# Error scenarios for testing
ERROR_SCENARIOS = {
    "invalid_site": {
        "site_name": ["invalid_site"],
        "search_term": "test"
    },
    "invalid_job_type": {
        "site_name": ["indeed"],
        "search_term": "test",
        "job_type": "invalid_type"
    },
    "invalid_country": {
        "site_name": ["indeed"],
        "search_term": "test",
        "country_indeed": "INVALID"
    },
    "negative_results": {
        "site_name": ["indeed"],
        "search_term": "test",
        "results_wanted": -1
    }
}

def get_sample_dataframe(num_jobs: int = 3) -> pd.DataFrame:
    """Get a sample DataFrame with specified number of jobs."""
    if num_jobs == 0:
        return pd.DataFrame(columns=SAMPLE_JOBS_DF.columns)
    
    # Repeat and modify sample data if more jobs needed
    jobs_data = SAMPLE_JOBS_DATA * ((num_jobs // len(SAMPLE_JOBS_DATA)) + 1)
    jobs_data = jobs_data[:num_jobs]
    
    # Add variation to repeated data
    for i, job in enumerate(jobs_data):
        if i >= len(SAMPLE_JOBS_DATA):
            job = job.copy()
            job["TITLE"] = f"{job['TITLE']} {i}"
            job["JOB_URL"] = f"{job['JOB_URL']}-{i}"
    
    return pd.DataFrame(jobs_data)

def get_sample_search_params(scenario: str = "basic_search") -> Dict[str, Any]:
    """Get sample search parameters for different scenarios."""
    return SAMPLE_SEARCH_PARAMS.get(scenario, SAMPLE_SEARCH_PARAMS["basic_search"]).copy()

def get_error_scenario(scenario: str) -> Dict[str, Any]:
    """Get error scenario parameters for testing."""
    return ERROR_SCENARIOS.get(scenario, {}).copy()