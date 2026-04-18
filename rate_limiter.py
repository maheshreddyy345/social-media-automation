"""Rate limiter for the reply bot.

All limits operate on the canonical posted set: rows in `candidate_replies`
where status == 'posted'. We read this fresh each check — the table is
small and indexed."""

import os
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func
from dotenv import load_dotenv

from models.database import SessionLocal, CandidateReply

load_dotenv()

IST = timezone(timedelta(hours=5, minutes=30))

DAILY_CAP = int(os.getenv("REPLY_BOT_DAILY_CAP", "20"))
MIN_SPACING_MIN = int(os.getenv("REPLY_BOT_MIN_SPACING_MIN", "8"))
AUTHOR_COOLDOWN_HOURS = int(os.getenv("REPLY_BOT_AUTHOR_COOLDOWN_HOURS", "6"))
CAMPAIGN_PER_HOUR = int(os.getenv("REPLY_BOT_CAMPAIGN_PER_HOUR", "2"))
ACTIVE_WINDOW_START = int(os.getenv("REPLY_BOT_ACTIVE_START_IST", "8"))
ACTIVE_WINDOW_END = int(os.getenv("REPLY_BOT_ACTIVE_END_IST", "23"))


@dataclass
class RateDecision:
    allowed: bool
    reason: Optional[str] = None


def _ist_now() -> datetime:
    return datetime.now(tz=IST)


def _in_active_window(now_ist: datetime) -> bool:
    h = now_ist.hour
    return ACTIVE_WINDOW_START <= h < ACTIVE_WINDOW_END


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def enabled() -> bool:
    return os.getenv("REPLY_BOT_ENABLED", "true").lower() in ("1", "true", "yes")


def can_post_now(target_author: str, campaign_name: Optional[str]) -> RateDecision:
    """Evaluate all rules. Call this right before posting, not at draft time."""
    if not enabled():
        return RateDecision(False, "kill switch off")

    now_ist = _ist_now()
    if not _in_active_window(now_ist):
        return RateDecision(
            False,
            f"outside active window {ACTIVE_WINDOW_START:02d}:00-{ACTIVE_WINDOW_END:02d}:00 IST",
        )

    now = _utc_now()
    day_cutoff = now - timedelta(hours=24)
    spacing_cutoff = now - timedelta(minutes=MIN_SPACING_MIN)
    author_cutoff = now - timedelta(hours=AUTHOR_COOLDOWN_HOURS)
    hour_cutoff = now - timedelta(hours=1)

    db = SessionLocal()
    try:
        daily = (
            db.query(func.count(CandidateReply.id))
            .filter(CandidateReply.status == "posted")
            .filter(CandidateReply.posted_at >= day_cutoff)
            .scalar()
            or 0
        )
        if daily >= DAILY_CAP:
            return RateDecision(False, f"daily cap reached ({daily}/{DAILY_CAP})")

        last = (
            db.query(func.max(CandidateReply.posted_at))
            .filter(CandidateReply.status == "posted")
            .scalar()
        )
        if last and last >= spacing_cutoff:
            return RateDecision(False, f"min spacing {MIN_SPACING_MIN}m not elapsed")

        if target_author:
            author_hit = (
                db.query(func.count(CandidateReply.id))
                .filter(CandidateReply.status == "posted")
                .filter(CandidateReply.target_author == target_author)
                .filter(CandidateReply.posted_at >= author_cutoff)
                .scalar()
                or 0
            )
            if author_hit > 0:
                return RateDecision(
                    False, f"author @{target_author} cooldown ({AUTHOR_COOLDOWN_HOURS}h)"
                )

        if campaign_name:
            camp_hit = (
                db.query(func.count(CandidateReply.id))
                .filter(CandidateReply.status == "posted")
                .filter(CandidateReply.campaign_name == campaign_name)
                .filter(CandidateReply.posted_at >= hour_cutoff)
                .scalar()
                or 0
            )
            if camp_hit >= CAMPAIGN_PER_HOUR:
                return RateDecision(
                    False,
                    f"campaign {campaign_name} hit {camp_hit}/hr cap",
                )

        return RateDecision(True)
    finally:
        db.close()


def posted_in_last_24h() -> int:
    db = SessionLocal()
    try:
        return (
            db.query(func.count(CandidateReply.id))
            .filter(CandidateReply.status == "posted")
            .filter(CandidateReply.posted_at >= _utc_now() - timedelta(hours=24))
            .scalar()
            or 0
        )
    finally:
        db.close()


if __name__ == "__main__":
    d = can_post_now("bjp4india", campaign_name=None)
    print(f"allowed={d.allowed} reason={d.reason}")
    print(f"posted in last 24h: {posted_in_last_24h()}")
