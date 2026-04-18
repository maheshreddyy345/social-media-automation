from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, BigInteger, Index
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


class CandidateReply(Base):
    __tablename__ = "candidate_replies"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String, index=True)  # bjp | keyword | trending
    campaign_name = Column(String, index=True, nullable=True)
    target_tweet_id = Column(String, index=True)
    target_tweet_url = Column(String)
    target_author = Column(String, index=True)
    target_text = Column(Text)
    drafted_text = Column(Text, nullable=True)
    status = Column(String, index=True, default="pending_draft")
    # pending_draft | pending_approval | approved | posted | skipped | post_failed | dropped
    telegram_message_id = Column(BigInteger, nullable=True)
    telegram_chat_id = Column(BigInteger, nullable=True)
    regen_count = Column(Integer, default=0)
    posted_url = Column(String, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)


class CampaignState(Base):
    __tablename__ = "campaigns_state"

    name = Column(String, primary_key=True)
    posts_today = Column(Integer, default=0)
    last_reset_at = Column(DateTime, default=datetime.utcnow)


class RateLimitState(Base):
    __tablename__ = "rate_limit_state"

    key = Column(String, primary_key=True)  # global | author:<handle> | campaign:<name>
    window_start = Column(DateTime, default=datetime.utcnow)
    count = Column(Integer, default=0)


class SeenTweetId(Base):
    __tablename__ = "seen_tweet_ids"

    tweet_id = Column(String, primary_key=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
