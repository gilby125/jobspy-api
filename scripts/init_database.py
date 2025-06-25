#!/usr/bin/env python3
"""
Database initialization script to create all required tables.
This script can be run in the container to set up the database schema.
"""
import sys
import logging
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from app.db.database import create_tables, check_database_connection, init_database
from app.models.tracking_models import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Initialize the database with all required tables."""
    try:
        logger.info("Starting database initialization...")
        
        # Initialize database connection
        init_database()
        logger.info("Database connection initialized")
        
        # Check database connection
        if not check_database_connection():
            logger.error("Database connection failed")
            return 1
        
        logger.info("Database connection verified")
        
        # Create all tables
        logger.info("Creating database tables...")
        create_tables()
        logger.info("Database tables created successfully")
        
        # List all tables that were created
        from app.db.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            logger.info(f"Created tables: {', '.join(tables)}")
        
        logger.info("Database initialization completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())