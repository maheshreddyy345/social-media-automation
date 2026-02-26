from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# GCP Cloud SQL Connection String
# Format: postgresql://username:password@public_ip:5432/dbname
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "SocialMediaBotPassword2026!")
DB_HOST = os.getenv("DB_HOST", "localhost")  # We will update this once GCP provisions the IP
DB_NAME = os.getenv("DB_NAME", "postgres")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ContentLog(Base):
    __tablename__ = "content_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    source_url = Column(String, unique=True, index=True)
    headline = Column(String)
    politician = Column(String)
    drafted_thread = Column(Text)  # JSON array of tweets
    media_paths = Column(Text)     # Comma separated media paths

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
