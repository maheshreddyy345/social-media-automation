import os
import time
import requests
import tweepy
from dotenv import load_dotenv

def run_engagement_agent():
    """Builds a standalone Quote-Tweeting agent focused on destroying PR."""
    print("═"*60)
    print("  ⚔️  ENGAGEMENT AGENT v2.0 — Propaganda Slayer")
    print("═"*60)
    
    load_dotenv()
    
    # Check if we have Twitter API keys
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    if not consumer_key:
        print("  ⚠️ Twitter API keys missing. Cannot run Engagement Agent.")
        return
        
    client = tweepy.Client(
        consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
        consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
        access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    )
    
    # 1. Target a specific handle (e.g., official PR handles)
    target_handle = "bjp4india"  # Hardcoded for the example, can be dynamic later
    print(f"[1/3] 🎯 Hunting Target: @{target_handle}...")
    
    try:
        user_info = client.get_user(username=target_handle)
        if not user_info or not user_info.data:
            print("  ❌ Could not find target user.")
            return
            
        target_id = user_info.data.id
        
        # 2. Get their most recent tweet (excluding RTs and replies if possible)
        tweets = client.get_users_tweets(id=target_id, max_results=5, exclude=['retweets', 'replies'])
        if not tweets or not tweets.data:
            print(f"  😴 Target @{target_handle} hasn't posted anything new.")
            return
            
        target_tweet = tweets.data[0]
        tweet_text = target_tweet.text
        tweet_id = target_tweet.id
        
        print(f"  → Found Target Tweet ({tweet_id}):\n    \"{tweet_text[:100]}...\"")
        
    except Exception as e:
        print(f"  ❌ Error fetching target tweet: {e}")
        return

    # 3. Generate the Dunk using Grok-4-1
    print("[2/3] 🧠 Generating devastating Quote-Tweet response via Grok-4-1...")
    
    system_prompt = (
        "You are the fearless voice of the @Sawalkaro accountability channel.\n"
        "You have been provided with a PR tweet from the ruling Indian government (BJP).\n"
        "Your job is to Quote-Tweet them by instantly destroying their claim with hard facts, broken promises, or systemic reality.\n"
        "Keep it under 250 characters. Be sharp, sarcastic, and brutal. DO NOT use hashtags.\n"
        "Return ONLY the text of the Quote-Tweet, nothing else."
    )
    
    headers = {
        "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "grok-4-1-fast-reasoning",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Target PR Tweet: \"{tweet_text}\""}
        ],
        "temperature": 0.85,
    }
    
    try:
        response = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        dunk_text = response.json()["choices"][0]["message"]["content"].strip().strip('"')
        print(f"  → Generated Dunk:\n    {dunk_text}")
    except Exception as e:
        print(f"  ❌ Error generating response: {e}")
        return
        
    # 4. Execute the Quote-Tweet
    print("[3/3] ⚔️ Executing Quote-Tweet...")
    try:
        # To quote-tweet in Tweepy V2, pass the tweet_id in quote_tweet_id
        response = client.create_tweet(text=dunk_text, quote_tweet_id=tweet_id)
        qt_id = response.data['id']
        qt_url = f"https://x.com/anyuser/status/{qt_id}"
        print(f"  ✅ Quote-Tweet successful! URL: {qt_url}")
        
    except Exception as e:
        print(f"  ❌ Error executing Quote-Tweet: {e}")

if __name__ == "__main__":
    run_engagement_agent()
