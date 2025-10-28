from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Import the settings object
from config import settings

# Use the DATABASE_URL from the centralized settings
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG_MODE, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base for declarative models
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()