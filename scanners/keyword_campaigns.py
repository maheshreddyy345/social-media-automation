"""Scans Twitter for active campaigns defined in config/campaigns.yaml.

Runs every 30 min as a systemd oneshot."""

import sys
import yaml
from datetime import date
from pathlib import Path

from ._base import make_client, enqueue_candidate

CAMPAIGNS_YAML = Path(__file__).resolve().parent.parent / "config" / "campaigns.yaml"


def _load_campaigns():
    with open(CAMPAIGNS_YAML, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    return doc.get("campaigns", [])


def _campaign_active(camp, today: date) -> bool:
    if not camp.get("enabled", True):
        return False
    start = camp.get("start_date")
    end = camp.get("end_date")
    if start and today < start:
        return False
    if end and today > end:
        return False
    return True


def _build_query(camp) -> str:
    kws = camp.get("keywords") or []
    # Quote each phrase so multi-word terms work. OR them together.
    or_clause = " OR ".join(f'"{k}"' for k in kws)
    # Filter: English or Hindi, exclude retweets, exclude replies to keep the list focused.
    return f"({or_clause}) -is:retweet -is:reply lang:en"


def _has_excluded(text: str, excludes) -> bool:
    low = text.lower()
    return any(e.lower() in low for e in (excludes or []))


def scan_once() -> int:
    client = make_client()
    today = date.today()
    campaigns = _load_campaigns()
    total = 0

    for camp in campaigns:
        if not _campaign_active(camp, today):
            continue
        name = camp["name"]
        min_likes = int(camp.get("min_likes", 0))
        max_per_scan = int(camp.get("max_per_scan", 5))
        excludes = camp.get("exclude_keywords", [])

        try:
            resp = client.search_recent_tweets(
                query=_build_query(camp),
                max_results=50,
                tweet_fields=["public_metrics", "author_id", "lang", "created_at"],
                expansions=["author_id"],
                user_fields=["username"],
            )
        except Exception as e:
            print(f"[kw_scanner] search failed for {name}: {e}", file=sys.stderr)
            continue
        if not resp or not resp.data:
            continue

        # Map author_id -> username from the includes block.
        username_by_id = {}
        for u in (resp.includes or {}).get("users", []) or []:
            username_by_id[u.id] = u.username

        # Sort by likes desc so the best candidates get queued first under the cap.
        ranked = sorted(
            resp.data,
            key=lambda t: (t.public_metrics or {}).get("like_count", 0),
            reverse=True,
        )

        queued_for_camp = 0
        for tw in ranked:
            if queued_for_camp >= max_per_scan:
                break
            likes = (tw.public_metrics or {}).get("like_count", 0)
            if likes < min_likes:
                continue
            if _has_excluded(tw.text, excludes):
                continue
            author = username_by_id.get(tw.author_id, str(tw.author_id))
            if enqueue_candidate(
                source="keyword",
                tweet_id=str(tw.id),
                author=author,
                text=tw.text,
                campaign_name=name,
            ):
                queued_for_camp += 1
                total += 1
                print(f"[kw_scanner] queued {name}/@{author}/{tw.id} (likes={likes})")

    return total


if __name__ == "__main__":
    n = scan_once()
    print(f"[kw_scanner] inserted {n} candidates")
