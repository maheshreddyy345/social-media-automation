import os
import json
import tweepy
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from crew import AccountabilityCrew
from models.database import init_db, SessionLocal, ContentLog
from models.post import ThreadResult

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Twitter / X
TWITTER_CONSUMER_KEY = os.getenv('TWITTER_CONSUMER_KEY')
TWITTER_CONSUMER_SECRET = os.getenv('TWITTER_CONSUMER_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

def send_telegram_message(text: str):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }, timeout=15)

def publish_thread_to_twitter(thread_result: ThreadResult):
    print("\n[PUBLISHER] 🐦 Connecting to X API (V1.1 + V2)...")
    
    # Needs auth configuration
    client = tweepy.Client(
        consumer_key=TWITTER_CONSUMER_KEY,
        consumer_secret=TWITTER_CONSUMER_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )

    auth = tweepy.OAuth1UserHandler(
        TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
    )
    api = tweepy.API(auth)
    
    # 1. Upload Media
    media_ids = []
    if getattr(thread_result, 'media_path', None) and os.path.exists(thread_result.media_path):
        print(f"  --> Uploading Media: {thread_result.media_path}")
        media = api.media_upload(filename=thread_result.media_path)
        media_ids.append(media.media_id)
        
    # 2. Chain tweets together
    previous_tweet_id = None
    
    for i, tweet_text in enumerate(thread_result.tweets):
        kwargs = {"text": tweet_text}
        
        # Attach media only to the first tweet
        if i == 0 and media_ids:
            kwargs["media_ids"] = media_ids
            
        # Reply to previous tweet if not first
        if previous_tweet_id:
            kwargs["in_reply_to_tweet_id"] = previous_tweet_id
            
        print(f"  --> Posting Tweet {i+1}/{len(thread_result.tweets)}")
        response = client.create_tweet(**kwargs)
        previous_tweet_id = response.data['id']
        
    print("[PUBLISHER] ✅ Thread Published successfully!")

def main():
    print("╔════════════════════════════════════════╗")
    print("║ Sawaal Karo - V6 (Enterprise CrewAI)   ║")
    print("╚════════════════════════════════════════╝\n")

    # 1. Init Database
    print("[SYSTEM] 🐘 Connecting to Cloud SQL PostgreSQL...")
    init_db()

    # 2. Launch the Crew
    print("[SYSTEM] 🤖 Launching Writer's Room Crew...")
    crew = AccountabilityCrew()
    
    # CrewAI kickoff returns a structured dict since we mapped tasks to Pydantic models
    # but the final output is from the last agent (Thread Architect)
    raw_result = crew.run()
    
    # Note: CrewAI Crew Outputs might be raw text depending on process, but we told The Architect to output ThreadResult JSON.
    try:
        # Pydantic JSON string parsing
        if hasattr(raw_result, 'json_dict'):
             thread_data = raw_result.json_dict
        else:
             import json
             import re
             clean = re.sub(r"^```json\s*|```$", "", str(raw_result), flags=re.MULTILINE).strip()
             thread_data = json.loads(clean)
             
        thread_result = ThreadResult(**thread_data)
    except Exception as e:
        print(f"[ERROR] Failed to parse Thread Result: {e}")
        print(f"Raw Output: {raw_result}")
        return

    # 3. Save to DB
    print("[SYSTEM] 💾 Archiving payload into PostgreSQL database...")
    db = SessionLocal()
    new_log = ContentLog(
        headline="CrewAI Multi-Agent Output",
        drafted_thread=json.dumps(thread_result.tweets)
    )
    db.add(new_log)
    db.commit()
    db.close()

    # 4. Notify Telegram
    if TELEGRAM_CHAT_ID:
        send_telegram_message("📢 <b>V6 ENTERPRISE CREW FINISHED DRAFTING THREAD</b>\n\nI have attached the payload to Cloud SQL. Review terminal for details.")

    # 5. Native Thread Publishing
    print("\n[SYSTEM] Starting publisher pipeline...")
    # publish_thread_to_twitter(thread_result) # Skipping live post during test
    print(thread_result.tweets)
    print("\n✅ V6 Pipeline Complete.")

if __name__ == "__main__":
    main()
