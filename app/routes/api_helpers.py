"""Helper functions for API routes."""
from datetime import datetime

def parse_date_posted(date_value):
    """Parse date_posted field which can be string or date object."""
    if not date_value:
        return None
    
    # If it's already a date object, return it
    if hasattr(date_value, 'year'):
        return date_value
    
    # If it's a string, try to parse it
    try:
        return datetime.strptime(str(date_value), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None