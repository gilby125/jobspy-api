from sqlalchemy.orm import Session

from app.models.tracking_models import JobPosting, Company, Location, JobCategory, ScrapingRun
from app import schemas
from app.core.logging_config import get_logger

logger = get_logger("db.crud")

def get_items(db: Session, skip: int = 0, limit: int = 100):
    logger.debug(f"DB query: get_items(skip={skip}, limit={limit})")
    try:
        result = db.query(JobPosting).offset(skip).limit(limit).all()
        logger.debug(f"DB query successful, returned {len(result)} records")
        return result
    except Exception as e:
        logger.exception(f"DB query failed: {str(e)}")
        raise

def create_item(db: Session, item: schemas.ItemCreate):
    logger.debug(f"DB operation: create_item with data: {item.dict()}")
    try:
        db_item = JobPosting(**item.dict())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        logger.debug(f"DB operation successful, created item with id: {db_item.id}")
        return db_item
    except Exception as e:
        db.rollback()
        logger.exception(f"DB operation failed, rolling back: {str(e)}")
        raise