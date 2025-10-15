# models/__init__.py

# Import the shared Base from database.py
from database import Base

# Import your model classes so Alembic sees them
from .phoneuser import PhoneUsers
from .schedule import Schedule

# Explicitly define what gets exported if someone does "from models import ..."
__all__ = ["Base", "PhoneUsers", "Schedule"]