"""Watches India trending topics for hooks that match our stance.

Runs every 60 min. Uses tweepy v1.1 get_place_trends (v2 doesn't expose
trends), then v2 search_recent_tweets inside matching trends."""

import os
import sys
import tweepy
from dotenv import load_dotenv

from ._base import make_client, enqueue_candidate

load_dotenv()

INDIA_WOEID = 23424848

# Trend keywords we engage on. Case-insensitive substring match against trend name.
STANCE_KEYWORDS = [
    "adani",
    "farmer",
    "modi",
    "bjp",
    "manipur",
    "unemployment",
    "inflation",
    "gst",
    "demonet",
    "electoral bond",
    "cbi",
    "ed raid",
    "pegasus",
    "hindenburg",
    "jumla",
]

MIN_LIKES = 50
MAX_PER_TREND = 2


def _v1_client() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        os.getenv("TWITTER_CONSUMER_KEY"),
        os.getenv("TWITTER_CONSUMER_SECRET"),
        os.getenv("TWITTER_ACCESS_TOKEN"),
        os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
    )
    return tweepy.API(auth)


def _matches_stance(trend_name: str) -> bool:
    low = trend_name.lower()
    return any(k in low for k in STANCE_KEYWORDS)


def scan_once() -> int:
    v1 = _v1_client()
    try:
        trends_resp = v1.get_place_trends(INDIA_WOEID)
    except Exception as e:
        print(f"[trend_scanner] get_place_trends failed: {e}", file=sys.stderr)
        return 0
    if not trends_resp:
        return 0

    trends = trends_resp[0].get("trends", []) if isinstance(trends_resp, list) else []
    hits = [t for t in trends if _matches_stance(t.get("name", ""))]
    if not hits:
        return 0

    v2 = make_client()
    total = 0

    for trend in hits[:5]:  # cap to 5 trends per tick
        q = f'"{trend["name"]}" -is:retweet -is:reply lang:en'
        try:
            resp = v2.search_recent_tweets(
                query=q,
                max_results=25,
                tweet_fields=["public_metrics", "author_id"],
                expansions=["author_id"],
                user_fields=["username"],
            )
        except Exception as e:
            print(f"[trend_scanner] search failed for {trend['name']}: {e}", file=sys.stderr)
            continue
        if not resp or not resp.data:
            continue

        username_by_id = {
            u.id: u.username for u in (resp.includes or {}).get("users", []) or []
        }

        ranked = sorted(
            resp.data,
            key=lambda t: (t.public_metrics or {}).get("like_count", 0),
            reverse=True,
        )
        queued = 0
        for tw in ranked:
            if queued >= MAX_PER_TREND:
                break
            likes = (tw.public_metrics or {}).get("like_count", 0)
            if likes < MIN_LIKES:
                continue
            author = username_by_id.get(tw.author_id, str(tw.author_id))
            if enqueue_candidate(
                source="trending",
                tweet_id=str(tw.id),
                author=author,
                text=tw.text,
                campaign_name=f"trend:{trend['name'][:40]}",
            ):
                queued += 1
                total += 1
                print(f"[trend_scanner] queued {trend['name']}/@{author}/{tw.id} (likes={likes})")

    return total


if __name__ == "__main__":
    n = scan_once()
    print(f"[trend_scanner] inserted {n} candidates")
