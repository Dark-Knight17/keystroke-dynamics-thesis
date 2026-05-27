import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/keystroke_db")

# Diagnostic: Print DB Host (safely)
try:
    from urllib.parse import urlparse
    parsed = urlparse(SQLALCHEMY_DATABASE_URL)
    print(f"DATABASE DIAGNOSTIC - Connecting to host: {parsed.hostname}", flush=True)
except Exception as e:
    print(f"DATABASE DIAGNOSTIC - Could not parse URL: {str(e)}", flush=True)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
