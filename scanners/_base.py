"""Shared scanner primitives.

Scanners produce candidate reply rows. All three scanners (BJP handles,
keyword campaigns, trending watch) write into the same `candidate_replies`
table via `enqueue_candidate`, deduping against `seen_tweet_ids`."""

import os
import tweepy
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from models.database import SessionLocal, CandidateReply, SeenTweetId

load_dotenv()


def make_client() -> tweepy.Client:
    bearer = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer:
        raise RuntimeError("TWITTER_BEARER_TOKEN not set")
    return tweepy.Client(bearer_token=bearer, wait_on_rate_limit=True)


def tweet_url(handle: str, tweet_id: str) -> str:
    return f"https://x.com/{handle}/status/{tweet_id}"


def enqueue_candidate(
    source: str,
    tweet_id: str,
    author: str,
    text: str,
    campaign_name: Optional[str] = None,
) -> bool:
    """Insert a pending_draft candidate if tweet_id is new. Returns True if inserted."""
    db = SessionLocal()
    try:
        if db.query(SeenTweetId).filter_by(tweet_id=tweet_id).first():
            return False
        db.add(SeenTweetId(tweet_id=tweet_id, first_seen_at=datetime.utcnow()))
        db.add(
            CandidateReply(
                source=source,
                campaign_name=campaign_name,
                target_tweet_id=tweet_id,
                target_tweet_url=tweet_url(author, tweet_id),
                target_author=author,
                target_text=text,
                status="pending_draft",
            )
        )
        db.commit()
        return True
    finally:
        db.close()
