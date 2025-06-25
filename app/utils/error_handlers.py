"""Error handling utilities for the API."""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from app.utils.validation_helpers import generate_error_suggestions

logger = logging.getLogger(__name__)

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors in a consistent way."""
    error_details = []
    for error in exc.errors():
        error_details.append({
            "location": error["loc"],
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(f"Validation error: {error_details}")
    
    # Generate helpful suggestions
    suggestions = generate_error_suggestions(error_details)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "details": error_details,
            "path": request.url.path,
            "suggestions": suggestions,
            "documentation_url": "/docs"
        }
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent response format."""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    
    # Create a content object with standard fields
    content = {
        "error": "Request Error",
        "status_code": exc.status_code,
        "message": exc.detail,
        "path": request.url.path
    }
    
    # Add suggestions for common errors
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        if "API Key" in exc.detail:
            content["suggestions"] = [{
                "parameter": "x-api-key",
                "message": "Missing or invalid API key",
                "suggestion": "Include a valid API key in the x-api-key header",
                "documentation_url": "/docs#section/Authentication"
            }]
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        if "Page" in exc.detail and "not found" in exc.detail:
            content["suggestions"] = [{
                "parameter": "page",
                "message": "Page number out of range",
                "suggestion": "Use a page number within the available range",
            }]
    
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions with consistent response format."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    # Create basic error response
    content = {
        "error": "Server Error",
        "message": str(exc),
        "path": request.url.path
    }
    
    # Add suggestions based on exception type or message
    if "scrape_jobs" in str(exc):
        content["suggestions"] = [{
            "message": "Error occurred during job scraping",
            "suggestion": "Check your search parameters and try again with fewer job boards or results",
            "troubleshooting": "Try using only one job site at a time (e.g., site_name=linkedin)" 
        }]
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content
    )
