"""Scans the latest tweets from BJP official handles and key ministers.

Runs as a oneshot under a systemd timer every 15 min."""

import sys
from ._base import make_client, enqueue_candidate

# Pre-resolved to avoid burning get_user calls each tick.
# Source: verified handles as of 2026-04.
BJP_HANDLES = {
    "bjp4india": "35773039",
    "narendramodi": "18839785",
    "AmitShah": "493924639",
    "JPNadda": "103651748",
    "nsitharaman": "156932962",       # Finance Minister Nirmala Sitharaman
    "DrSJaishankar": "46007989",      # External Affairs Minister S. Jaishankar
    "PiyushGoyal": "82751669",        # Commerce & Industry Minister
    "AshwiniVaishnaw": "842273927",   # Railways & IT Minister
    "smritiirani": "228039500",       # Smriti Irani
}


def scan_once() -> int:
    """Fetch latest tweets from each handle, enqueue unseen ones. Returns count inserted."""
    client = make_client()
    inserted = 0
    for handle, user_id in BJP_HANDLES.items():
        try:
            resp = client.get_users_tweets(
                id=user_id,
                max_results=5,
                exclude=["retweets", "replies"],
                tweet_fields=["created_at", "public_metrics"],
            )
        except Exception as e:
            print(f"[bjp_scanner] error fetching @{handle}: {e}", file=sys.stderr)
            continue
        if not resp or not resp.data:
            continue
        for tw in resp.data:
            if enqueue_candidate(
                source="bjp",
                tweet_id=str(tw.id),
                author=handle,
                text=tw.text,
            ):
                inserted += 1
                print(f"[bjp_scanner] queued @{handle}/{tw.id}")
    return inserted


if __name__ == "__main__":
    n = scan_once()
    print(f"[bjp_scanner] inserted {n} candidates")
