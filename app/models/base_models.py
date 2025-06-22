"""Base models for testing and simple operations."""
from sqlalchemy import Column, Integer, String, Text
from app.models.tracking_models import Base


class Item(Base):
    """Simple example model for testing CRUD operations."""
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)