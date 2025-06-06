import csv
import io
import logging
import os
import time
import uuid
from typing import List, Optional, Union

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.cache import cache
from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware, log_request_middleware
from app.routes import api, health
from app.utils.env_debugger import log_environment_settings
from app.utils.error_handlers import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

# Determine log level from environment - priority to "LOG_LEVEL" over "DEBUG" flag for consistency
log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
try:
    log_level = getattr(logging, log_level_name)
except AttributeError:
    print(f"WARNING: Invalid LOG_LEVEL: {log_level_name}, using INFO")
    log_level = logging.INFO

# Setup logging with determined level
setup_logging(log_level)
logger = get_logger("main")

logger.info(f"Starting application with log level: {log_level_name}")

# Add version info for deployment tracking
import subprocess
import os
try:
    # Try to get git commit hash
    git_commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], 
                                       stderr=subprocess.DEVNULL, 
                                       cwd='/app').decode().strip()
    git_branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                       stderr=subprocess.DEVNULL, 
                                       cwd='/app').decode().strip()
    logger.info(f"🚀 JobSpy API Version: {git_branch}@{git_commit}")
except:
    logger.info("🚀 JobSpy API Version: Unknown (git not available)")

# Add deployment timestamp
from datetime import datetime
logger.info(f"📅 Deployment Time: {datetime.now().isoformat()}")

# Set Uvicorn's access logger to WARNING to avoid logging health checks
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

SUPPORTED_SITES = ["indeed", "linkedin", "zip_recruiter", "glassdoor", "google", "bayt", "naukri"]

def get_env_bool(var_name, default=True):
    val = os.getenv(var_name)
    if val is None:
        return default
    return str(val).lower() in ("1", "true", "yes", "on")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services, connections, etc.
    logger.info("Starting up JobSpy Docker API")
    
    # Log environment variables to help debugging
    log_environment_settings()
    
    # Yield control to the application
    yield
    
    # Shutdown: Clean up resources
    logger.info("Shutting down JobSpy Docker API")
    cache.clear()

# Create FastAPI app with enhanced documentation
app = FastAPI(
    title="JobSpy Docker API",
    description="""
    # JobSpy Docker API
    
    An API for searching jobs across multiple platforms including LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, Bayt, and Naukri.
    
    ## Authentication
    
    All API endpoints require an API key to be passed in the `x-api-key` header.
    
    ## Rate Limiting
    
    Requests are limited based on your API key. The default limit is 100 requests per hour.
    
    ## Caching
    
    Results are cached for 1 hour by default to improve performance and reduce load on job board sites.
    """,
    version="1.0.0",
    lifespan=lifespan,
    # Configure docs endpoints based on settings
    docs_url=settings.SWAGGER_UI_PATH if settings.ENABLE_SWAGGER_UI else None,
    redoc_url=settings.REDOC_PATH if settings.ENABLE_REDOC else None,
    openapi_tags=[
        {
            "name": "Jobs",
            "description": "Operations related to job searching",
        },
        {
            "name": "Health",
            "description": "API health check endpoints",
        },
        {
            "name": "Info",
            "description": "General API information",
        },
    ],
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Job Spy FastAPI application")
    
    # Set API key auth
    global ENABLE_API_KEY_AUTH
    ENABLE_API_KEY_AUTH = get_env_bool("ENABLE_API_KEY_AUTH", default=True)
    if ENABLE_API_KEY_AUTH:
        logger.info("API key authentication is enabled")
    else:
        logger.warning("API key authentication is disabled. Set ENABLE_API_KEY_AUTH=true to enable.")
    
    # Additional startup logic

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Job Spy FastAPI application")
    # Additional shutdown logic can be added here

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Add request logging middleware
app.add_middleware(RequestLoggerMiddleware)

# Add exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Add request timing and logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Generate request ID for tracking
    request_id = str(uuid.uuid4())
    logger.debug(f"Request {request_id} started: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.debug(
            f"Request {request_id} completed: {request.method} {request.url.path} "
            f"- Status: {response.status_code} - Time: {process_time:.3f}s"
        )
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        logger.exception(f"Request {request_id} failed: {str(e)}")
        raise

# Include routers
app.include_router(api.router, prefix="/api/v1", tags=["Jobs"])
app.include_router(health.router, tags=["Health"])

# Include advanced jobs API router with database integration
try:
    from app.api.routes import jobs
    app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Advanced Jobs"])
    logger.info("Advanced jobs API router loaded successfully")
except ImportError as e:
    logger.warning(f"Could not load advanced jobs router: {e}")

# Add admin routes
try:
    from app.routes import admin
    app.include_router(admin.router, prefix="/admin", tags=["Admin"])
    logger.info("Admin routes loaded successfully")
except ImportError as e:
    logger.warning(f"Could not load admin routes: {e}")
    # Create a simple admin endpoint instead
    @app.get("/admin/")
    async def simple_admin():
        return {"message": "Admin panel temporarily unavailable", "error": str(e)}

@app.get("/", tags=["Info"])
def read_root():
    return {
        "message": "Welcome to JobSpy Docker API!",
        "docs_url": "/docs",
        "api_root": "/api/v1",
        "health_check": "/health"
    }


# API key auth default logic (at app startup or dependency)
ENABLE_API_KEY_AUTH = get_env_bool("ENABLE_API_KEY_AUTH", default=True)
if not ENABLE_API_KEY_AUTH:
    import warnings
    warnings.warn("API key authentication is disabled. Set ENABLE_API_KEY_AUTH=true to enable.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
