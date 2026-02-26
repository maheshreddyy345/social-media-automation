from langchain.tools import tool
import tweepy
import os
import json
from dotenv import load_dotenv

load_dotenv()

target_accounts = [
    "AltNews", "zoo_bear", "dhruv_rathee", "RTI_India", "SaketGokhale", 
    "ravishndtv", "thewire_in", "suchetadalal", "thecaravanindia", "newslaundry",
    "pbhushan1", "RanaAyyub", "SupriyaShrinate", "Jairam_Ramesh", "scribe_prashant",
    "Kisanektamorcha", "MahuaMoitra"
]

@tool("Scrape Critical Tweets")
def scrape_critical_tweets() -> str:
    """Useful to scrape the latest political and infrastructure news from targeted independent journalists on X/Twitter. Returns a JSON string of tweets."""
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        return json.dumps({"error": "TWITTER_BEARER_TOKEN not found."})

    client = tweepy.Client(bearer_token=bearer_token)
    all_tweets = []

    for handle in target_accounts:
        try:
            user = client.get_user(username=handle)
            if not user or not user.data:
                continue

            user_id = user.data.id
            tweets = client.get_users_tweets(
                id=user_id,
                max_results=5,
                exclude=["retweets", "replies"],
                tweet_fields=["created_at", "public_metrics"],
                expansions=["attachments.media_keys"],
                media_fields=["url", "type", "alt_text", "variants", "duration_ms"]
            )

            if not tweets.data:
                continue

            media_dict = {m.media_key: m for m in tweets.includes.get("media", [])} if tweets.includes else {}

            for tweet in tweets.data:
                media_list = []
                if tweet.attachments and "media_keys" in tweet.attachments:
                    for mk in tweet.attachments["media_keys"]:
                        m = media_dict.get(mk)
                        if m:
                            duration = m.get("duration_ms", 0)
                            if duration > 120000:
                                continue # Skip videos longer than 2 mins
                                
                            video_url = None
                            if m.type == "video" and hasattr(m, "variants") and m.variants:
                                mp4_variants = sorted(
                                    [v for v in m.variants if v.get("content_type") == "video/mp4" and v.get("bit_rate")],
                                    key=lambda x: x.get("bit_rate", 0), reverse=True
                                )
                                if mp4_variants:
                                    video_url = mp4_variants[0].get("url")
                            
                            media_list.append({
                                "type": m.type,
                                "url": video_url if m.type == "video" else getattr(m, "url", None)
                            })
                
                # Only keep tweets with real media
                if media_list:
                    all_tweets.append({
                        "source": handle,
                        "url": f"https://twitter.com/{handle}/status/{tweet.id}",
                        "text": tweet.text,
                        "metrics": tweet.public_metrics,
                        "media": media_list
                    })
        except Exception as e:
            continue

    return json.dumps(all_tweets[:30])
