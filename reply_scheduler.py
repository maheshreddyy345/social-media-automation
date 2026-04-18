"""Long-running scheduler.

- Every 30s: drain pending_draft → draft with Claude → pending_approval → Telegram.
- Every 5min: sweep approved candidates, check rate limits, post via OpenClaw.

The scheduler does NOT scan Twitter — that's the scanners' job (cron-fired).
It only processes the queue the scanners populate."""

import sys
import time
import traceback
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import asc

from models.database import SessionLocal, CandidateReply
from reply_generator import generate_with_retry, ReplyRejected
from rate_limiter import can_post_now, enabled, posted_in_last_24h, DAILY_CAP
from telegram_reply import send_reply_candidate, send_plain

DRAFT_BATCH = 3          # draft at most N per tick (cost control)
POST_BATCH = 1           # post at most N per tick (spacing handled by rate_limiter)
DRAFT_INTERVAL_SEC = 30
POST_INTERVAL_SEC = 300
CAP_ALERT_THRESHOLD = 0.9


def _next_pending_drafts(limit: int):
    db = SessionLocal()
    try:
        return (
            db.query(CandidateReply)
            .filter(CandidateReply.status == "pending_draft")
            .order_by(asc(CandidateReply.created_at))
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def _next_approved(limit: int):
    db = SessionLocal()
    try:
        return (
            db.query(CandidateReply)
            .filter(CandidateReply.status == "approved")
            .order_by(asc(CandidateReply.created_at))
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def _update_row(cid: int, **fields) -> CandidateReply:
    db = SessionLocal()
    try:
        row = db.query(CandidateReply).get(cid)
        if not row:
            return None
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def draft_tick():
    if not enabled():
        return
    rows = _next_pending_drafts(DRAFT_BATCH)
    for r in rows:
        print(f"[sched] drafting candidate #{r.id} (@{r.target_author})")
        try:
            draft = generate_with_retry(
                target_text=r.target_text,
                target_author=r.target_author,
                source=r.source,
                campaign_stance=None,  # campaign_stance wired in Phase 3
            )
        except ReplyRejected as e:
            print(f"[sched] dropped #{r.id}: {e}", file=sys.stderr)
            _update_row(r.id, status="dropped", error=str(e))
            continue
        except Exception as e:
            print(f"[sched] draft error #{r.id}: {e}", file=sys.stderr)
            traceback.print_exc()
            continue

        updated = _update_row(
            r.id, drafted_text=draft.text, status="pending_approval"
        )
        try:
            resp = send_reply_candidate(updated)
            msg = resp.get("result") or {}
            _update_row(
                r.id,
                telegram_message_id=msg.get("message_id"),
                telegram_chat_id=(msg.get("chat") or {}).get("id"),
            )
        except Exception as e:
            print(f"[sched] telegram push failed for #{r.id}: {e}", file=sys.stderr)


def post_tick():
    if not enabled():
        return

    posted = posted_in_last_24h()
    if posted >= DAILY_CAP:
        return
    if posted == int(DAILY_CAP * CAP_ALERT_THRESHOLD):
        send_plain(f"⚠️ Reply bot at {posted}/{DAILY_CAP} for the day.")

    rows = _next_approved(POST_BATCH)
    if not rows:
        return

    # Defer import so a missing openclaw install doesn't break the draft loop
    from openclaw_poster import post_reply

    for r in rows:
        decision = can_post_now(r.target_author, r.campaign_name)
        if not decision.allowed:
            print(f"[sched] skipping #{r.id}: {decision.reason}")
            return  # cool off: try again next tick

        print(f"[sched] posting #{r.id} via OpenClaw")
        try:
            posted_url = post_reply(r)
        except Exception as e:
            print(f"[sched] post error #{r.id}: {e}", file=sys.stderr)
            _update_row(r.id, status="post_failed", error=str(e))
            send_plain(f"❌ Reply #{r.id} failed to post: {e}")
            continue

        _update_row(
            r.id,
            status="posted",
            posted_url=posted_url,
            posted_at=datetime.utcnow(),
        )
        send_plain(f"✅ Reply #{r.id} posted: {posted_url}")


def main():
    print(f"[sched] starting. daily cap={DAILY_CAP}. enabled={enabled()}")
    sched = BlockingScheduler()
    sched.add_job(draft_tick, "interval", seconds=DRAFT_INTERVAL_SEC, id="draft", max_instances=1)
    sched.add_job(post_tick, "interval", seconds=POST_INTERVAL_SEC, id="post", max_instances=1)
    sched.start()


if __name__ == "__main__":
    main()
