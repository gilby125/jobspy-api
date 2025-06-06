"""Pydantic schemas for API request/response validation."""
from typing import Optional
from pydantic import BaseModel


class ItemBase(BaseModel):
    """Base item schema."""
    title: str
    description: Optional[str] = None


class ItemCreate(ItemBase):
    """Schema for creating items."""
    pass


class ItemUpdate(ItemBase):
    """Schema for updating items."""
    title: Optional[str] = None


class Item(ItemBase):
    """Schema for item responses."""
    id: int
    
    class Config:
        from_attributes = True