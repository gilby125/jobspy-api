"""Database configuration and session management with TimescaleDB support."""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Defer database initialization until needed
engine = None
SessionLocal = None

def get_database_url():
    """Get database URL with validation."""
    database_url = settings.DATABASE_URL
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return database_url

def init_database():
    """Initialize database engine and session factory."""
    global engine, SessionLocal
    
    if engine is not None:
        return  # Already initialized
    
    database_url = get_database_url()
    
    # Production-ready engine configuration
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=20,  # Connection pool size
        max_overflow=30,  # Additional connections beyond pool_size
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,  # Recycle connections every hour
        echo=settings.LOG_LEVEL.upper() == "DEBUG",  # Log SQL in debug mode
        connect_args={
            "options": "-c timezone=utc",  # Ensure UTC timezone
            "application_name": "jobspy_tracking_system"
        }
    )
    
    # Configure session factory
    SessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=engine,
        expire_on_commit=False  # Keep objects usable after commit
    )
    
    # Register event listeners
    register_event_listeners()


# Import tracking models to register them with Base
try:
    from app.models.tracking_models import Base
    logger.info("Tracking models imported successfully")
except ImportError as e:
    logger.warning(f"Could not import tracking models: {e}")
    # Fall back to empty Base if models can't be imported
    Base = declarative_base()

def get_db():
    """
    Get a database session with proper error handling.
    
    Yields:
        Session: SQLAlchemy database session
    """
    init_database()  # Ensure database is initialized
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def create_tables():
    """Create all tables in the database."""
    init_database()  # Ensure database is initialized
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def check_database_connection():
    """Check if database connection is working."""
    init_database()  # Ensure database is initialized
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

def register_event_listeners():
    """Register database event listeners after engine is created."""
    if engine is None:
        return
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set pragmas for SQLite connections (for testing)."""
        if "sqlite" in str(dbapi_connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    @event.listens_for(engine, "first_connect")
    def setup_timescaledb(dbapi_connection, connection_record):
        """Setup TimescaleDB-specific configurations on first connect."""
        try:
            cursor = dbapi_connection.cursor()
            
            # Check if TimescaleDB is available
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
            timescale_available = cursor.fetchone()[0]
            
            if timescale_available:
                logger.info("TimescaleDB extension detected")
                
                # This will be handled by Alembic migrations, but we can verify setup
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM timescaledb_information.hypertables 
                        WHERE hypertable_name = 'company_hiring_trends'
                    )
                """)
                hypertable_exists = cursor.fetchone()[0]
                
                if hypertable_exists:
                    logger.info("TimescaleDB hypertables configured")
                else:
                    logger.info("TimescaleDB hypertables will be created by migrations")
            else:
                logger.warning("TimescaleDB extension not found - time-series features may be limited")
            
            cursor.close()
        except Exception as e:
            logger.warning(f"TimescaleDB setup check failed: {e}")
