"""
Social Media Automation Engine - Phase 1 + 2
=============================================
Fetches hot Indian political news via Perplexity,
drafts a sharp post with OpenAI GPT-4o,
generates an image with gpt-image-1 (OpenAI's best model),
sends to Telegram for approval, and saves locally.
"""

import os
import re
import json
import time
import base64
import requests
import tweepy
import feedparser
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
PERPLEXITY_API_KEY  = os.getenv("PERPLEXITY_API_KEY")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")

# ── Validate keys up front ───────────────────────────────────────────────────
def validate_config():
    missing = []
    if not os.getenv("XAI_API_KEY"):
        missing.append("XAI_API_KEY")
    if not TELEGRAM_BOT_TOKEN or "your_telegram_bot" in TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
        
    for k in ["TWITTER_CONSUMER_KEY", "TWITTER_CONSUMER_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET", "FAL_KEY"]:
        if not os.getenv(k):
            missing.append(k)

    if missing:
        raise EnvironmentError(
            f"Missing API keys in .env: {', '.join(missing)}\n"
            "Please update your .env file and try again."
        )

# ── Clients ──────────────────────────────────────────────────────────────────
# Using OpenAI library but pointing to xAI for Grok-2 (uncensored, fearless analysis)
xai_client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)


# ═══════════════════════════════════════════════════════════════════════════
# AGENT 1: THE SCRAPER (RSS Feed Extractor)
# ═══════════════════════════════════════════════════════════════════════════
def agent1_scrape_rss() -> list:
    """Scrapes top Indian independent media RSS feeds for the latest political news."""
    print("\n[1/4] 🕷️  AGENT 1 (Scraper): Gathering raw intelligence from independent Indian media...")
    
    rss_feeds = [
        {"name": "The Wire", "url": "https://thewire.in/rss"},
        {"name": "The Hindu (National)", "url": "https://www.thehindu.com/news/national/feeder/default.rss"},
        {"name": "Deccan Herald (National)", "url": "https://www.deccanherald.com/national/rssfeed.xml"},
        {"name": "NDTV (Latest)", "url": "https://feeds.feedburner.com/ndtvnews-latest"},
        {"name": "Livemint (Politics)", "url": "https://www.livemint.com/rss/politics"}
    ]

    all_headlines = []
    
    # Keyword filter to only grab highly relevant, hard-hitting stories
    keywords = ["collapse", "scam", "leak", "corruption", "protest", "unemployment", "inflation", "bridge", "hospital", "modi", "bjp", "congress", "railway", "infrastructure", "debt", "crisis", "arrest"]

    for source in rss_feeds:
        try:
            feed = feedparser.parse(source["url"])
            if not feed.entries:
                continue
                
            # Take up to 15 recent articles per feed
            for entry in feed.entries[:15]:
                title = entry.title
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                
                # Simple keyword check
                combined_text = (title + " " + summary).lower()
                if any(kw in combined_text for kw in keywords):
                    all_headlines.append({
                        "source": source["name"],
                        "title": title,
                        "url": link,
                        "summary": summary[:300] + "..." if len(summary) > 300 else summary
                    })
        except Exception as e:
            print(f"  ❌ Error scraping {source['name']}: {e}")

    print(f"  → Agent 1 gathered {len(all_headlines)} highly relevant news articles.")
    return all_headlines

# ═══════════════════════════════════════════════════════════════════════════
# AGENT 2: THE CURATOR (Grok-2 News Evaluator)
# ═══════════════════════════════════════════════════════════════════════════
def agent2_curate_news(headlines: list) -> dict:
    """Uses Grok-2 to score all scraped headlines and pick the absolute worst government failure."""
    print("[2/4] 🧠 AGENT 2 (Curator): Scoring articles and selecting the most devastating daily failure with Grok-2...")

    if not headlines:
        raise ValueError("No headlines found to curate!")

    # Format headlines into a numbered list
    formatted_list = ""
    for idx, item in enumerate(headlines):
        formatted_list += f"[{idx}] SOURCE: {item['source']} | TITLE: {item['title']} | URL: {item.get('url', 'N/A')} | SUMMARY: {item['summary']}\n\n"

    system_prompt = (
        "You are the ruthless Editor-in-Chief of the @Sawalkaro accountability channel, with a specific focus on the last 12 years of BJP governance.\n"
        "You have a list of recent news articles. Select the single most impactful, devastating story that clearly demonstrates systemic government failure, infrastructure collapse, or massive corruption.\n\n"
        "SCORING RUBRIC:\n"
        "- 15 points: Massive financial scams with specific amounts, infrastructure collapse, or catastrophic policy failures directly linking to the ruling party.\n"
        "- 10 points: Broken promises vs reality, severe economic distress (unemployment/inflation) affecting common citizens.\n"
        "- 5 points: General political controversy, standard protests.\n"
        "- 0 points: Generic political speeches, PR, or irrelevant news.\n\n"
        "Return ONLY a factual JSON object with these exact keys: \n"
        '{"headline": "...", "summary": "...", "source": "...", "url": "...", "systemic_link": "...", "key_fact": "...", "politicians_involved": "..."}'
    )

    user_query = f"Here is the raw intelligence feed from the last 24 hours:\n\n{formatted_list}\n\nAnalyze this list, score them internally, and return the JSON object for the absolute most damning story."

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
    story_data = json.loads(clean)
    
    print(f"  → Agent 2 selected: {story_data.get('headline', 'N/A')}")
    return story_data


# ═══════════════════════════════════════════════════════════════════════════
# AGENT 1.5: THE READER (HTML Full Text Extractor)
# ═══════════════════════════════════════════════════════════════════════════
def agent1_5_extract_full_text(url: str) -> str:
    """Navigates to the news article URL and extracts the core paragraph text."""
    if not url or url == "N/A":
        return ""
    print(f"[2.5] 📖 AGENT 1.5 (Reader): Extracting full article context from: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        paragraphs = soup.find_all('p')
        full_text = " ".join([p.get_text(strip=True) for p in paragraphs])
        
        if len(full_text) > 15000:
            full_text = full_text[:15000] + "... [TRUNCATED]"
            
        print(f"  → Agent 1.5 extracted {len(full_text)} characters of detailed facts.")
        return full_text
    except Exception as e:
        print(f"  ❌ Agent 1.5 Error extracting text: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# AGENT 2.5: THE VERIFIER (Fact Checking)
# ═══════════════════════════════════════════════════════════════════════════
def agent2_5_verify_facts(news_data: dict) -> dict:
    """Uses DDG search to double-check the key facts and numbers before posting."""
    print("[2.5] 🔍 AGENT 2.5 (Verifier): Cross-checking facts against the live web...")
    
    headline = news_data.get('headline', '')
    if not headline:
        print("  ⚠️ No headline to verify, skipping.")
        return news_data
        
    try:
        search_query = f"{headline} news"
        results = DDGS().text(search_query, max_results=3)
        
        verification_context = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        print(f"  → Verified against {len(results)} live web sources.")
        
        # Append verification context
        news_data['verification_context'] = verification_context
        return news_data
    except Exception as e:
        print(f"  ❌ Verification Error (Continuing anyway): {e}")
        news_data['verification_context'] = "Web search verification failed or timed out."
        return news_data

# ═══════════════════════════════════════════════════════════════════════════
# AGENT 3: THE DRAFTER (Grok-4-1)
# ═══════════════════════════════════════════════════════════════════════════
def generate_post_text(news_data: dict) -> dict:
    """Generates Twitter + Instagram post text and an image prompt."""
    print("[3/4] ✍️  AGENT 3 (Drafter): Writing the analytical long-form post...")

    system_prompt = (
        "You are the fearless voice of @Sawalkaro. Your tone is sharp, sarcastic, and brutally honest, with deep empathy for the common man.\n"
        "You must always include context connecting this issue to the last 12 years of BJP governance when the facts support it. Never shy away from naming Modi or specific ministers.\n\n"
        "CHOOSE EXACTLY ONE OF THESE FORMATS based on the story:\n"
        "1. Devastating News Thread (Hook + Bullets + 'Sawaal Karo' demand)\n"
        "2. Witty Hypothetical (Satirical opening + facts)\n"
        "3. Broken Promise Timeline (Year X promised vs Year Y reality)\n"
        "4. Citizen Story Empathy Bomb (Victim focused + systemic collapse)\n"
        "5. Propaganda Slayer (Dismantling a PR claim)\n\n"
        "Return ONLY a JSON object with these keys: \n"
        '{"chosen_format": "...", "twitter_post": "...", "instagram_post": "...", "image_prompt": "..."}\n\n'
        "POST RULES:\n"
        "- Make it highly readable and punchy.\n"
        "- CRITICAL: DO NOT use any hashtags anywhere. Zero hashtags.\n"
        "- Be brutally sharp, but 100% factual.\n\n"
        "IMAGE PROMPT RULES (CRITICAL):\n"
        "- ALWAYS include this exact string at the end of your image prompt:\n"
        '"Editorial political cartoon in the bold sharp satirical style of R.K. Laxman and Satish Acharya, hand-drawn black ink lines with subtle watercolor wash, clean minimalist white background, high contrast, exaggerated but not grotesque caricature, include the iconic silent Common Man (balding middle-aged Indian in dhoti + checked coat, round spectacles) standing in foreground observing the absurdity, newspaper cartoon quality, masterpiece, highly detailed clean lines, no text anywhere, no speech bubbles, no labels."\n'
        "- The metaphor must be purely visual. NO text or real names in the image."
    )

    user_message = (
        f"News Headline: {news_data.get('headline', 'N/A')}\n"
        f"Summary: {news_data.get('summary', 'N/A')}\n"
        f"Key Fact: {news_data.get('key_fact', 'N/A')}\n"
        f"Systemic Link to ruling party: {news_data.get('systemic_link', 'N/A')}\n"
        f"Politicians Involved: {news_data.get('politicians_involved', 'N/A')}\n"
        f"People Affected: {news_data.get('affected_people', 'N/A')}\n"
        f"Source: {news_data.get('source', 'N/A')}\n"
        f"URL: {news_data.get('url', 'N/A')}\n\n"
        f"--- FULL ARTICLE CONTEXT ---\n"
        f"{news_data.get('full_article_text', '')}\n"
        f"--- VERIFICATION DATA (LIVE WEB) ---\n"
        f"{news_data.get('verification_context', 'No verification data.')}\n"
        f"----------------------------"
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
    print(f"  → Post generated ✅ (Keys found: {list(result.keys())})")
    
    # Failsafe: if image_prompt is missing or empty, provide a default
    if not result.get("image_prompt"):
        print("  ⚠️ Warning: GPT-4o returned empty image_prompt. Supplying failsafe prompt.")
        result["image_prompt"] = "A clever, hand-drawn Indian newspaper political cartoon showing a giant politician ignoring a struggling common man. Watercolor caricature style, no text or words."
        
    return result


# ═══════════════════════════════════════════════════════════════════════════
# AGENT 4: THE ARTIST (xAI Native Image Gen)
# ═══════════════════════════════════════════════════════════════════════════
def generate_image(image_prompt: str, output_dir: Path) -> Path:
    """
    Generates a high-quality image using xAI's native grok-imagine-image model via the OpenAI SDK.
    Returns the local path to the saved image.
    """
    print("[4/4] 🎨 AGENT 4 (Artist): Generating Satish Acharya cartoon via xAI Native API...")

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.x.ai/v1",
            api_key=os.getenv("XAI_API_KEY")
        )

        try:
            response = client.images.generate(
                model="grok-imagine-image",
                prompt=image_prompt,
                n=1
            )
            image_url = response.data[0].url
        except Exception as api_err:
            print(f"  ❌ xAI API Error Details: {api_err}")
            raise api_err

        # Download the image
        img_bytes = requests.get(image_url, timeout=30).content
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path  = output_dir / f"post_image_{timestamp}.jpg"
        img_path.write_bytes(img_bytes)
        print(f"  → Image saved locally: {img_path} ✅")
        return img_path
    except Exception as e:
        print(f"  ❌ Agent 4 Error generating image via xAI: {e}")
        raise e


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: SAVE DRAFT LOCALLY
# ═══════════════════════════════════════════════════════════════════════════
def save_post_locally(news_data: dict, post_data: dict, img_path: Path, output_dir: Path) -> Path:
    """Saves the full draft post as a readable .txt file."""
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    post_file  = output_dir / f"post_draft_{timestamp}.txt"

    content = f"""
╔══════════════════════════════════════════════════════════════════╗
                    📢 DRAFT POST — {datetime.now().strftime("%d %b %Y %I:%M %p")}
╚══════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━
📰 SOURCE NEWS & V2 CURATION
━━━━━━━━━━━━━━━━━━━━━━
Headline : {news_data.get('headline', 'N/A')}
Summary  : {news_data.get('summary', 'N/A')}
Systemic : {news_data.get('systemic_link', 'N/A')}
Key Fact : {news_data.get('key_fact', 'N/A')}
Affected : {news_data.get('affected_people', 'N/A')}
Source   : {news_data.get('source', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━
🐦 TWITTER POST (Format: {post_data.get('chosen_format', 'Standard')})
━━━━━━━━━━━━━━━━━━━━━━
{post_data.get('twitter_post', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━
📸 INSTAGRAM POST
━━━━━━━━━━━━━━━━━━━━━━
{post_data.get('instagram_post', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━
🖼️  IMAGE
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
    """Sends a text message to your Telegram chat. Returns message_id."""
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }, timeout=15)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def send_telegram_photo(img_path: Path, caption: str) -> int:
    """Sends the generated image with a caption. Returns message_id."""
    with open(img_path, "rb") as f:
        r = requests.post(f"{TELEGRAM_API}/sendPhoto", data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
        }, files={"photo": f}, timeout=30)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def send_telegram_approval_prompt(draft_id: str) -> int:
    """Sends approval buttons to Telegram. Returns message_id."""
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": (
            f"⏳ <b>Post Draft Ready for Review</b>\n"
            f"Draft ID: <code>{draft_id}</code>\n\n"
            f"Choose an action:"
        ),
        "parse_mode": "HTML",
        "reply_markup": json.dumps({
            "inline_keyboard": [[
                {"text": "✅ Approve & Schedule", "callback_data": f"approve_{draft_id}"},
                {"text": "🔄 Regenerate",         "callback_data": f"regen_{draft_id}"},
                {"text": "⏭️ Skip",               "callback_data": f"skip_{draft_id}"},
            ]]
        })
    }
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def wait_for_telegram_decision(draft_id: str, timeout_secs: int = 1800) -> str:
    """
    Polls Telegram every 2 seconds for a button tap (callback_query) OR a
    text command (approve / regen / skip). Responds instantly to both.
    Returns 'approve', 'regen', or 'skip'.
    """
    print(f"\n🕐 Waiting for your Telegram decision (timeout: {timeout_secs//60} min)...")
    print("   Tip: Tap a button OR simply reply: approve / regen / skip")

    last_update_id = None
    start_time     = time.time()

    # Map of text keywords → action
    TEXT_ACTIONS = {
        "approve": "approve", "yes": "approve", "ok": "approve", "✅": "approve",
        "regen":   "regen",   "regenerate": "regen", "redo": "regen", "🔄": "regen",
        "skip":    "skip",    "no": "skip",  "next": "skip",  "⏭": "skip",
    }

    while time.time() - start_time < timeout_secs:
        # Short timeout = near-instant response to button taps
        params = {
            "timeout": 2,
            "allowed_updates": ["callback_query", "message"],
        }
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

            # ── Handle button tap (inline keyboard) ──────────────────────────
            cb = update.get("callback_query")
            if cb:
                data = cb.get("data", "")
                if draft_id in data:
                    action = "_".join(data.split("_")[:-2]) if data.startswith("regen_format_") or data.startswith("convert_quote_") else data.split("_")[0]
                    # Instant pop-up acknowledgment on the button
                    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
                        "callback_query_id": cb["id"],
                        "text": {"approve": "✅ Approved!",
                                 "regen":   "🔄 Regenerating all...",
                                 "regen_format": "🎲 Changing format...",
                                 "convert_quote": "⚔️ Converting to Quote...",
                                 "skip":    "⏭️ Skipped"}.get(action, "Got it!"),
                        "show_alert": False,
                    }, timeout=5)
                    # Confirmation message in chat
                    action_label = {"approve": "✅ Approved! Post scheduled.",
                                    "regen":   "🔄 Regenerating a completely new post...",
                                    "regen_format": "🎲 Redrafting in a new format...",
                                    "convert_quote": "⚔️ Converting text to a Quote-Tweet format...",
                                    "skip":    "⏭️ Skipped. Next post in 6 hours."}.get(action, "Got it!")
                    send_telegram_message(action_label)
                    return action

            # ── Handle text reply (typed command) ────────────────────────────
            msg = update.get("message", {})
            if msg and str(msg.get("chat", {}).get("id", "")) == str(TELEGRAM_CHAT_ID):
                text = msg.get("text", "").strip().lower()
                action = TEXT_ACTIONS.get(text)
                if action:
                    action_label = {"approve": "✅ Approved! Post scheduled.",
                                    "regen":   "🔄 Regenerating a new post...",
                                    "skip":    "⏭️ Skipped. Next post in 6 hours."}.get(action, "Got it!")
                    send_telegram_message(action_label)
                    return action

    print("⏰ Decision timeout — defaulting to skip.")
    send_telegram_message("⏰ No response received in 30 min. Skipping this post.")
    return "skip"

def send_to_telegram_for_approval(news_data: dict, post_data: dict, img_path: Path) -> str:
    """
    Sends the full draft to Telegram with an approval prompt.
    Returns the decision: 'approve', 'regen', or 'skip'.
    """
    if not TELEGRAM_CHAT_ID or "your_telegram_chat" in (TELEGRAM_CHAT_ID or ""):
        print("⚠️  TELEGRAM_CHAT_ID not set — skipping Telegram approval.")
        return "skip"

    draft_id  = datetime.now().strftime("%Y%m%d_%H%M%S")
    headline  = news_data.get("headline", "N/A")
    systemic  = news_data.get("systemic_link", "N/A")
    format_c  = post_data.get("chosen_format", "Standard")

    # 1. Send the news context
    send_telegram_message(
        f"🇮🇳 <b>V2 DRAFT READY FOR REVIEW</b>\n\n"
        f"📰 <b>News:</b> {headline}\n"
        f"🔗 <b>Systemic:</b> {systemic}\n"
        f"📊 <b>Key Fact:</b> {news_data.get('key_fact', 'N/A')}"
    )

    # 2. Send the generated image (no caption to avoid length limits)
    send_telegram_photo(img_path, caption="(Image generated for this post)")

    # 3. Send the long-form Twitter post
    twitter_post = post_data.get("twitter_post", "")
    send_telegram_message(f"🐦 <b>Twitter ({format_c}):</b>\n\n{twitter_post}")

    # 4. Send the Instagram post
    ig_post = post_data.get("instagram_post", "")
    send_telegram_message(f"📸 <b>Instagram:</b>\n\n{ig_post}")

    # 5. Send approval buttons
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
            ],
            [
                {"text": "⚔️ Convert Quote", "callback_data": f"convert_quote_{draft_id}"}
            ]
        ]
    }
    
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "👆 <b>Action Required: Review the draft above.</b>",
        "parse_mode": "HTML",
        "reply_markup": keyboard
    }, timeout=15)

    # 6. Wait for your tap
    decision = wait_for_telegram_decision(draft_id)
    print(f"✅ Decision received: {decision.upper()}")
    return decision


# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: PUBLISH TO TWITTER
# ═══════════════════════════════════════════════════════════════════════════
def publish_to_twitter(post_text: str, img_path: Path) -> str:
    """Uploads image and publishes the tweet using Tweepy V1.1 (media) and V2 (tweet)."""
    print("\n[Phase 3] 🐦 Publishing to Twitter/X...")
    try:
        # V1.1 authentication (needed for media uploads)
        auth = tweepy.OAuth1UserHandler(
            os.getenv("TWITTER_CONSUMER_KEY"),
            os.getenv("TWITTER_CONSUMER_SECRET"),
            os.getenv("TWITTER_ACCESS_TOKEN"),
            os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )
        api = tweepy.API(auth)
        
        # Upload the image
        print("  → Uploading image to Twitter servers...")
        media = api.media_upload(filename=str(img_path))
        print("  → Image uploaded!")

        # V2 authentication (needed for creating tweets)
        client = tweepy.Client(
            consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
            consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )
        
        # Post the tweet with the uploaded media
        print("  → Posting tweet...")
        response = client.create_tweet(text=post_text, media_ids=[media.media_id])
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
    print("  🇮🇳  POLITICAL ACCOUNTABILITY ENGINE  — Starting Run")
    print("═"*60)

    # Step 1: Agent 1 scrapes the web
    raw_headlines = agent1_scrape_rss()

    # Step 2: Agent 2 curates the best story
    news_data = agent2_curate_news(raw_headlines)

    # Step 2.5: Agent 1.5 reads the full article for maximum detail
    article_url = news_data.get("url")
    if article_url and article_url != "N/A":
        news_data["full_article_text"] = agent1_5_extract_full_text(article_url)
    else:
        news_data["full_article_text"] = ""

    # Step 2.75: Agent 2.5 Verifies the key facts against the live web
    news_data = agent2_5_verify_facts(news_data)

    # Step 3: Agent 3 drafts the text based on the deep facts
    post_data = generate_post_text(news_data)

    # Step 4: Agent 4 generates the image
    img_path = generate_image(post_data.get("image_prompt", ""), output_dir)

    # Step 4: Save locally
    draft_file = save_post_locally(news_data, post_data, img_path, output_dir)
    print(f"  → Draft saved: {draft_file}")

    # Step 5: Send to Telegram for approval
    decision = send_to_telegram_for_approval(news_data, post_data, img_path)

    print("\n" + "═"*60)
    if decision == "approve":
        print("  ✅  POST APPROVED — Publishing now...")
        tweet_url = publish_to_twitter(post_data.get("twitter_post", ""), img_path)
        if tweet_url:
            send_telegram_message(f"🚀 <b>Live on Twitter!</b>\n{tweet_url}")
    elif decision == "regen":
        print("  🔄  REGENERATE ALL requested — Re-running pipeline...")
        run_pipeline()         # Recursively run again
        return
    elif decision == "regen_format":
        print("  🎲  REGENERATE FORMAT requested — Regenerating text/image only...")
        # Re-run from Agent 3 Draft step (skipping Agent 1 and 2 to save time/cost)
        new_post = generate_post_text(news_data)
        new_img = generate_image(new_post.get("image_prompt", ""), output_dir)
        send_to_telegram_for_approval(news_data, new_post, new_img)
        return
    elif decision == "convert_quote":
        print("  ⚔️  CONVERT requested — Engaging Propaganda Slayer...")
        # Note: In the future, this will link to Agent 2.5/Engagement Agent. For now, regenerating.
        new_post = generate_post_text(news_data)
        new_img = generate_image(new_post.get("image_prompt", ""), output_dir)
        send_to_telegram_for_approval(news_data, new_post, new_img)
        return
    else:
        print("  ⏭️  POST SKIPPED.")

    print(f"  📄  Draft: {draft_file}")
    print(f"  🖼️   Image: {img_path}")
    print("═"*60 + "\n")


if __name__ == "__main__":
    run_pipeline()
