"""API dependencies for FastAPI endpoints."""
from typing import Generator
from sqlalchemy.orm import Session

from app.db.database import get_db

# Re-export get_db for backwards compatibility
__all__ = ["get_db"]