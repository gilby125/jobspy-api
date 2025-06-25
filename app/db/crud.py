from sqlalchemy.orm import Session

from app.models.tracking_models import JobPosting
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

