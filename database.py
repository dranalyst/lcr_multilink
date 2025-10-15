# database.py

import psycopg2
from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base


# metadata = MetaData(schema="testCall")      # default schema for all tables
# Connection details (adjust if needed)
DB_NAME = "testCaller"
DB_USER = "postgres"
DB_PASS = "c6emcpostgres"
DB_HOST = "localhost"
DB_PORT = "5432"

# psycopg2 (for raw SQL if still needed)
def get_pg_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

# DB URL
DATABASE_URL = "postgresql://postgres:c6emcpostgres@localhost:5432/testCaller"

engine = create_engine(DATABASE_URL, echo=True, future=True)
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