"""
Social Media Automation Engine - V4: X-to-X Curation Pipeline
=============================================
Scrapes top independent Indian journalists on Twitter, curates the most
devastating data-driven tweet, rewrites it into the 'Sawaal Karo' format,
downloads the real attached media, and publishes it after Telegram approval.
"""

import os
import re
import json
import time
import requests
import tweepy
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Optional DDGS for fact checking
try:
    from duckduckgo_search import DDGS
except ImportError:
    pass

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")

# ── Validate keys up front ───────────────────────────────────────────────────
def validate_config():
    missing = []
    if not os.getenv("XAI_API_KEY"):
        missing.append("XAI_API_KEY")
    if not TELEGRAM_BOT_TOKEN or "your_telegram_bot" in TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
        
    for k in ["TWITTER_CONSUMER_KEY", "TWITTER_CONSUMER_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET", "TWITTER_BEARER_TOKEN"]:
        if not os.getenv(k):
            missing.append(k)

    if missing:
        raise EnvironmentError(
            f"Missing API keys in .env: {', '.join(missing)}\n"
            "Please update your .env file and try again."
        )

# ═══════════════════════════════════════════════════════════════════════════
# AGENT 1: THE SCRAPER (X Timeline Extractor)
# ═══════════════════════════════════════════════════════════════════════════
def agent1_scrape_x_timelines() -> list:
    """Scrapes latest tweets from top Indian independent media and data activists."""
    print("\n[1/4] 🕷️  AGENT 1 (Scraper): Gathering tweets from independent Indian critics...")
    
    target_accounts = [
        "AltNews", "zoo_bear", "dhruv_rathee", "RTI_India", "SaketGokhale", 
        "ravishndtv", "thewire_in", "suchetadalal", "thecaravanindia", "newslaundry"
    ]
    
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    client = tweepy.Client(bearer_token=bearer_token)
    
    all_tweets = []
    
    for username in target_accounts:
        try:
            user_response = client.get_user(username=username)
            if not user_response.data:
                continue
            
            user_id = user_response.data.id
            
            tweets_response = client.get_users_tweets(
                id=user_id,
                max_results=5,
                exclude=["retweets", "replies"],
                tweet_fields=["created_at", "public_metrics"],
                expansions=["attachments.media_keys"],
                media_fields=["url", "type", "variants", "preview_image_url"]
            )
            
            if not tweets_response.data:
                continue
                
            media_dict = {}
            if tweets_response.includes and 'media' in tweets_response.includes:
                for media in tweets_response.includes['media']:
                    media_dict[media.media_key] = media
                    
            for tweet in tweets_response.data:
                # We prioritize tweets WITH MEDIA (images or videos)
                if tweet.attachments and 'media_keys' in tweet.attachments:
                    media_items = []
                    for mk in tweet.attachments['media_keys']:
                        if mk in media_dict:
                            media = media_dict[mk]
                            m_url = media.url or media.preview_image_url
                            if media.type == 'video' and hasattr(media, 'variants'):
                                best_variant = None
                                highest_bitrate = -1
                                for variant in media.variants:
                                    if variant.get('content_type') == 'video/mp4':
                                        br = variant.get('bit_rate', 0)
                                        if br > highest_bitrate:
                                            highest_bitrate = br
                                            best_variant = variant.get('url')
                                if best_variant:
                                    m_url = best_variant
                            media_items.append({"type": media.type, "url": m_url})
                            
                    if media_items:
                        all_tweets.append({
                            "source": f"@{username}",
                            "text": tweet.text,
                            "media": media_items,
                            "metrics": tweet.public_metrics,
                            "url": f"https://twitter.com/{username}/status/{tweet.id}"
                        })
        except Exception as e:
            print(f"  ❌ Error scraping {username}: {e}")

    print(f"  → Agent 1 gathered {len(all_tweets)} media-rich tweets.")
    return all_tweets

# ═══════════════════════════════════════════════════════════════════════════
# AGENT 2: THE CURATOR (Grok-4-1)
# ═══════════════════════════════════════════════════════════════════════════
def agent2_curate_tweets(tweets: list) -> dict:
    """Uses Grok to score all scraped tweets and pick the absolute best one."""
    print("[2/4] 🧠 AGENT 2 (Curator): Scoring tweets and selecting the most devastating failure...")

    if not tweets:
        raise ValueError("No tweets with media found to curate!")

    formatted_list = ""
    for idx, item in enumerate(tweets):
        formatted_list += f"[{idx}] SOURCE: {item['source']} | URL: {item['url']} | TEXT: {item['text'][:300]}\n\n"

    system_prompt = (
        "You are the ruthless Editor-in-Chief of the @Sawalkaro accountability channel, focusing on the Indian government.\n"
        "You have a list of recent tweets from independent journalists. Select the single most impactful, devastating tweet that clearly demonstrates systemic government failure, infrastructure collapse, exposed data, or massive hypocrisy.\n\n"
        "SCORING:\n"
        "- 15 pts: Hard data, RTI replies, exposed documents, or infrastructure failure.\n"
        "- 10 pts: Logical takedown of government PR vs reality.\n"
        "- 5 pts: General controversy.\n"
        "Return ONLY a factual JSON object with these exact keys: \n"
        '{"selected_index": 0, "headline": "...", "key_fact": "...", "politicians_involved": "..."}'
    )

    user_query = f"Here is the raw intelligence feed from X:\n\n{formatted_list}\n\nAnalyze this list, pick the BEST index, and return the JSON object."

    headers = {
        "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "grok-4-1-fast-reasoning",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.3
    }
    
    response = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
    if response.status_code != 200:
        print(f"  ❌ Agent 2 API Error: {response.text}")
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"].strip()
    clean = re.sub(r"^```json\s*|```$", "", raw, flags=re.MULTILINE).strip()
    curation_result = json.loads(clean)
    
    selected_idx = curation_result.get("selected_index", 0)
    if selected_idx >= len(tweets) or selected_idx < 0:
        selected_idx = 0
        
    winning_tweet = tweets[selected_idx]
    
    story_data = {
        "source": winning_tweet["source"],
        "url": winning_tweet["url"],
        "original_text": winning_tweet["text"],
        "media": winning_tweet["media"],
        "metrics": winning_tweet["metrics"],
        "headline": curation_result.get("headline", "N/A"),
        "key_fact": curation_result.get("key_fact", "N/A"),
        "politicians_involved": curation_result.get("politicians_involved", "N/A")
    }
    
    print(f"  → Agent 2 selected Tweet from: {story_data['source']}\n  → Headline: {story_data['headline']}")
    return story_data

# ═══════════════════════════════════════════════════════════════════════════
# AGENT 2.5: THE VERIFIER (Fact Checking)
# ═══════════════════════════════════════════════════════════════════════════
def agent2_5_verify_facts(story_data: dict) -> dict:
    """Uses DDG search to double-check the key facts before posting."""
    print("[2.5] 🔍 AGENT 2.5 (Verifier): Cross-checking facts against the live web...")
    headline = story_data.get('headline', '')
    if not headline:
        return story_data
        
    try:
        search_query = f"{headline} news"
        results = DDGS().text(search_query, max_results=3)
        verification_context = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        print(f"  → Verified against {len(results)} live web sources.")
        story_data['verification_context'] = verification_context
        return story_data
    except Exception as e:
        print(f"  ❌ Verification Error (Continuing anyway): {e}")
        story_data['verification_context'] = "Web search verification failed or timed out."
        return story_data

# ═══════════════════════════════════════════════════════════════════════════
# AGENT 3: THE DRAFTER (Grok-4-1)
# ═══════════════════════════════════════════════════════════════════════════
def generate_post_text(story_data: dict) -> dict:
    """Generates Twitter + Instagram post text by rewriting the original tweet."""
    print("[3/4] ✍️  AGENT 3 (Drafter): Synthesizing the Sawaal Karo narrative...")

    system_prompt = (
        "You are the fearless voice of @Sawalkaro. Your tone is sharp, sarcastic, and brutally honest, with deep empathy for the common man.\n"
        "You must rewrite the provided original tweet into an entirely new, deeply analytical post. Do not just copy-paste their text. Extract the facts and construct a powerful narrative.\n\n"
        "CHOOSE EXACTLY ONE OF THESE FORMATS based on the story:\n"
        "1. Devastating News Thread (Hook + Bullets + 'Sawaal Karo' demand)\n"
        "2. Witty Hypothetical (Satirical opening + facts)\n"
        "3. Broken Promise Timeline (Year X promised vs Year Y reality)\n"
        "4. Citizen Story Empathy Bomb (Victim focused + systemic collapse)\n"
        "5. Propaganda Slayer (Dismantling a PR claim)\n\n"
        "Return ONLY a JSON object with these keys: \n"
        '{"chosen_format": "...", "twitter_post": "...", "instagram_post": "..."}\n\n'
        "POST RULES:\n"
        "- Tone MUST be highly conversational, natural, and human. Write exactly how a passionate, highly informed citizen would speak to a friend.\n"
        "- AVOID REPETITIVE PHRASES: Do NOT force phrases like '12 years of BJP governance' into every post. It sounds robotic. Instead, use accurate context (e.g., if the story is in Gujarat, mention their 26+ year rule; if it's railways, mention the specific minister; if it's national, refer to the Centre or Delhi).\n"
        "- Keep the narrative dynamic, unpredictable, and devastatingly logical.\n"
        "- DO NOT be overly dramatic or use cheap clickbait phrases.\n"
        "- Write LONG-FORM copy. Thoroughly explain the issue.\n"
        "- CRITICAL: DO NOT use any hashtags anywhere. Zero hashtags.\n"
        "- Always end by demanding accountability with the exact phrase 'Sawaal Karo'.\n"
        "- Cite the original source at the very end (e.g., 'Via [Source]')."
    )

    user_message = (
        f"Original Source: {story_data.get('source', 'N/A')}\n"
        f"Original Tweet Text: {story_data.get('original_text', 'N/A')}\n"
        f"Key Fact: {story_data.get('key_fact', 'N/A')}\n"
        f"Politicians Involved: {story_data.get('politicians_involved', 'N/A')}\n"
        f"Verification Context: {story_data.get('verification_context', 'N/A')}\n"
    )

    headers = {
        "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "grok-4-1-fast-reasoning",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.85
    }
    
    response = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
    if response.status_code != 200:
        print(f"  ❌ Agent 3 API Error: {response.text}")
        response.raise_for_status()

    result = json.loads(response.json()["choices"][0]["message"]["content"].strip())
    print(f"  → Post generated ✅")
    return result

# ═══════════════════════════════════════════════════════════════════════════
# AGENT 4: THE MEDIA HANDLER
# ═══════════════════════════════════════════════════════════════════════════
def agent4_download_media(media_list: list, output_dir: Path) -> Path:
    """Downloads the primary real media file from the tweet."""
    print("[4/4] 🖼️  AGENT 4 (Media Handler): Downloading authentic media from tweet...")
    
    if not media_list:
        print("  ⚠️ No media to download.")
        return None
        
    media = media_list[0]
    m_url = media.get("url")
    m_type = media.get("type")
    
    if not m_url:
        print("  ❌ Media URL is empty.")
        return None
        
    print(f"  --> Downloading {m_type}: {m_url}")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(m_url, headers=headers, timeout=30)
        r.raise_for_status()
        
        ext = ".mp4" if m_type == "video" else ".jpg"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        media_path = output_dir / f"post_real_media_{timestamp}{ext}"
        media_path.write_bytes(r.content)
        
        print(f"  → Real Media saved locally: {media_path} ✅")
        return media_path
    except Exception as e:
        print(f"  ❌ Error downloading media: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: SAVE DRAFT LOCALLY
# ═══════════════════════════════════════════════════════════════════════════
def save_post_locally(story_data: dict, post_data: dict, img_path: Path, output_dir: Path) -> Path:
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    post_file  = output_dir / f"post_draft_{timestamp}.txt"

    content = f"""
╔══════════════════════════════════════════════════════════════════╗
                    📢 V4 DRAFT POST — {datetime.now().strftime("%d %b %Y %I:%M %p")}
╚══════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━
📰 SOURCE TWEET & CURATION
━━━━━━━━━━━━━━━━━━━━━━
Source   : {story_data.get('source', 'N/A')}
Headline : {story_data.get('headline', 'N/A')}
Key Fact : {story_data.get('key_fact', 'N/A')}
URL      : {story_data.get('url', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━
🐦 TWITTER POST (Format: {post_data.get('chosen_format', 'Standard')})
━━━━━━━━━━━━━━━━━━━━━━
{post_data.get('twitter_post', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━
📸 INSTAGRAM POST
━━━━━━━━━━━━━━━━━━━━━━
{post_data.get('instagram_post', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━
🖼️  REAL MEDIA
━━━━━━━━━━━━━━━━━━━━━━
File     : {img_path}

━━━━━━━━━━━━━━━━━━━━━━
STATUS: PENDING APPROVAL
━━━━━━━━━━━━━━━━━━━━━━
"""
    post_file.write_text(content, encoding="utf-8")
    return post_file


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: SEND TO TELEGRAM FOR APPROVAL
# ═══════════════════════════════════════════════════════════════════════════
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_telegram_message(text: str) -> int:
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }, timeout=15)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def send_telegram_media(img_path: Path, caption: str) -> int:
    if not img_path or not img_path.exists():
        send_telegram_message("⚠️ No media was found for this post.")
        return 0
        
    is_video = str(img_path).endswith('.mp4')
    endpoint = "sendVideo" if is_video else "sendPhoto"
    file_type = "video" if is_video else "photo"
    
    with open(img_path, "rb") as f:
        r = requests.post(f"{TELEGRAM_API}/{endpoint}", data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
        }, files={file_type: f}, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def wait_for_telegram_decision(draft_id: str, timeout_secs: int = 1800) -> str:
    print(f"\n🕐 Waiting for your Telegram decision (timeout: {timeout_secs//60} min)...")
    print("   Tip: Tap a button OR simply reply: approve / regen / skip")

    last_update_id = None
    start_time     = time.time()
    TEXT_ACTIONS = {
        "approve": "approve", "yes": "approve", "ok": "approve", "✅": "approve",
        "regen":   "regen",   "regenerate": "regen", "redo": "regen", "🔄": "regen",
        "skip":    "skip",    "no": "skip",  "next": "skip",  "⏭": "skip",
    }

    while time.time() - start_time < timeout_secs:
        params = {"timeout": 2, "allowed_updates": ["callback_query", "message"]}
        if last_update_id is not None:
            params["offset"] = last_update_id + 1

        try:
            r = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=10)
            updates = r.json().get("result", [])
        except Exception:
            time.sleep(1)
            continue

        for update in updates:
            last_update_id = update["update_id"]
            cb = update.get("callback_query")
            if cb:
                data = cb.get("data", "")
                if draft_id in data:
                    action = "_".join(data.split("_")[:-2]) if data.startswith("regen_format_") or data.startswith("convert_quote_") else data.split("_")[0]
                    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
                        "callback_query_id": cb["id"],
                        "text": {"approve": "✅ Approved!", "regen": "🔄 Regenerating...", "skip": "⏭️ Skipped"}.get(action, "Got it!"),
                        "show_alert": False,
                    }, timeout=5)
                    action_label = {"approve": "✅ Approved! Post scheduled.", "regen": "🔄 Regenerating...", "regen_format": "🎲 Redrafting in a new format...", "skip": "⏭️ Skipped."}.get(action, "Got it!")
                    send_telegram_message(action_label)
                    return action

            msg = update.get("message", {})
            if msg and str(msg.get("chat", {}).get("id", "")) == str(TELEGRAM_CHAT_ID):
                text = msg.get("text", "").strip().lower()
                action = TEXT_ACTIONS.get(text)
                if action:
                    action_label = {"approve": "✅ Approved! Post scheduled.", "regen": "🔄 Regenerating...", "skip": "⏭️ Skipped."}.get(action, "Got it!")
                    send_telegram_message(action_label)
                    return action

    print("⏰ Decision timeout — defaulting to skip.")
    send_telegram_message("⏰ No response received in 30 min. Skipping this post.")
    return "skip"

def send_to_telegram_for_approval(story_data: dict, post_data: dict, img_path: Path) -> str:
    if not TELEGRAM_CHAT_ID: return "skip"

    draft_id  = datetime.now().strftime("%Y%m%d_%H%M%S")
    format_c  = post_data.get("chosen_format", "Standard")

    send_telegram_message(
        f"🇮🇳 <b>V4 DRAFT READY FOR REVIEW</b>\n\n"
        f"📰 <b>Source:</b> {story_data.get('source', 'N/A')}\n"
        f"📝 <b>Headline:</b> {story_data.get('headline', 'N/A')}\n"
        f"📊 <b>Original Tweet URL:</b> {story_data.get('url', 'N/A')}"
    )

    if img_path:
        send_telegram_media(img_path, caption="(Original Media Extracted from Tweet)")

    twitter_post = post_data.get("twitter_post", "")
    send_telegram_message(f"🐦 <b>Twitter ({format_c}):</b>\n\n{twitter_post}")

    print("  → Sending inline keyboard buttons...")
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve & Post", "callback_data": f"approve_{draft_id}"},
                {"text": "⏭️ Skip", "callback_data": f"skip_{draft_id}"}
            ],
            [
                {"text": "🔄 Regen All", "callback_data": f"regen_{draft_id}"},
                {"text": "🎲 Regen Format", "callback_data": f"regen_format_{draft_id}"}
            ]
        ]
    }
    
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "👆 <b>Action Required: Review the draft above.</b>",
        "parse_mode": "HTML",
        "reply_markup": keyboard
    }, timeout=15)

    decision = wait_for_telegram_decision(draft_id)
    print(f"✅ Decision received: {decision.upper()}")
    return decision


# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: PUBLISH TO TWITTER
# ═══════════════════════════════════════════════════════════════════════════
def publish_to_twitter(post_text: str, img_path: Path) -> str:
    print("\n[Phase 3] 🐦 Publishing to Twitter/X...")
    try:
        auth = tweepy.OAuth1UserHandler(
            os.getenv("TWITTER_CONSUMER_KEY"),
            os.getenv("TWITTER_CONSUMER_SECRET"),
            os.getenv("TWITTER_ACCESS_TOKEN"),
            os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )
        api = tweepy.API(auth)
        
        media_id = None
        if img_path and img_path.exists():
            print("  → Uploading underlying media to Twitter servers...")
            media = api.media_upload(filename=str(img_path))
            media_id = media.media_id
            print("  → Media uploaded!")

        client = tweepy.Client(
            consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
            consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )
        
        print("  → Posting tweet...")
        if media_id:
            response = client.create_tweet(text=post_text, media_ids=[media_id])
        else:
            response = client.create_tweet(text=post_text)
            
        tweet_id = response.data['id']
        tweet_url = f"https://x.com/anyuser/status/{tweet_id}"
        
        print(f"  ✅ Tweet published successfully! URL: {tweet_url}")
        return tweet_url
    except Exception as e:
        print(f"  ❌ Error publishing to Twitter: {e}")
        send_telegram_message(f"❌ <b>Twitter Post Failed</b>\n<pre>{str(e)}</pre>")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════
def run_pipeline():
    validate_config()

    output_dir = Path("drafts")
    output_dir.mkdir(exist_ok=True)

    print("\n" + "═"*60)
    print("  🇮🇳  POLITICAL ACCOUNTABILITY ENGINE V4 — Starting Run")
    print("═"*60)

    # Step 1: Agent 1 scrapes timelines
    raw_tweets = agent1_scrape_x_timelines()
    if not raw_tweets:
        print("Empty timeline feed! Skipping run.")
        return

    # Step 2: Agent 2 curates the best tweet
    story_data = agent2_curate_tweets(raw_tweets)

    # Step 2.5: Verify facts
    story_data = agent2_5_verify_facts(story_data)

    # Step 3: Draft the post
    post_data = generate_post_text(story_data)

    # Step 4: Download real media attached to the tweet
    img_path = agent4_download_media(story_data.get("media", []), output_dir)

    # Step 5: Save locally
    draft_file = save_post_locally(story_data, post_data, img_path, output_dir)

    # Step 6: Send to Telegram
    decision = send_to_telegram_for_approval(story_data, post_data, img_path)

    print("\n" + "═"*60)
    if decision == "approve":
        print("  ✅  POST APPROVED — Publishing now...")
        tweet_url = publish_to_twitter(post_data.get("twitter_post", ""), img_path)
        if tweet_url:
            send_telegram_message(f"🚀 <b>Live on Twitter!</b>\n{tweet_url}")
    elif decision == "regen":
        print("  🔄  REGENERATE ALL requested — Re-running pipeline...")
        run_pipeline()
        return
    elif decision == "regen_format":
        print("  🎲  REGENERATE FORMAT requested — Regenerating text...")
        new_post = generate_post_text(story_data)
        send_to_telegram_for_approval(story_data, new_post, img_path)
        return
    else:
        print("  ⏭️  POST SKIPPED.")

    print(f"  📄  Draft: {draft_file}")
    if img_path:
        print(f"  🖼️   Media: {img_path}")
    print("═"*60 + "\n")

if __name__ == "__main__":
    run_pipeline()
