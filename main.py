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
import fal_client

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
    if not OPENAI_API_KEY or "your_openai" in OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not PERPLEXITY_API_KEY or "your_perplexity" in PERPLEXITY_API_KEY:
        missing.append("PERPLEXITY_API_KEY")
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
openai_client = OpenAI(api_key=OPENAI_API_KEY)


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: FETCH NEWS via Perplexity API
# ═══════════════════════════════════════════════════════════════════════════
def fetch_latest_news() -> dict:
    """Queries Perplexity for the most impactful recent Indian political news."""
    print("\n[1/3] 📡 Fetching latest Indian political news from Perplexity...")

    system_prompt = (
        "You are an objective, data-driven research assistant for an Indian political news channel. "
        "Your job is to find the single most important BREAKING news story (strictly from the last 24-48 hours) "
        "that clearly demonstrates a recent failure of the government, infrastructure collapse, massive public protest, or immediate economic crisis. "
        "Do not return old statistical reports (like last month's data). We need current, actionable, burning issues occurring right now in India. "
        "You must extract hard data, specific monetary values, statistics, and the exact names of the public officials or institutions involved. "
        "Return ONLY a factual JSON object with these keys: "
        '{"headline": "...", "summary": "...", "source": "...", "key_fact": "...", "affected_people": "...", "politicians_involved": "..."}'
        " — Just the JSON, no extra text."
    )

    user_query = (
        "What is the most significant, breaking news story from India in the last 24 to 48 hours "
        "that clearly shows a failure of governance, infrastructure malfunction, or immediate crisis? "
        "Do not give me old data or general surveys. Give me a specific incident or policy failure that just happened. "
        "Pick the single most impactful story. Gather specific hard numbers and explicitly name the responsible authorities or leaders involved."
    )

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        "max_tokens": 600,
        "temperature": 0.3,
        "search_recency_filter": "day",
        "return_citations": False,
    }

    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"].strip()
    print(f"  → Perplexity found: {raw[:120]}...")

    clean = re.sub(r"^```json\s*|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(clean)


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: GENERATE POST TEXT via OpenAI GPT-4o
# ═══════════════════════════════════════════════════════════════════════════
def generate_post_text(news_data: dict) -> dict:
    """Generates Twitter + Instagram post text and an image prompt."""
    print("[2/3] ✍️  Drafting post text with GPT-4o...")

    system_prompt = (
        "You are a fearless, data-driven Indian political commentator running a highly influential "
        "social media accountability channel. Your goal is to systematically dismantle government "
        "propaganda and expose failures using logic, undeniable facts, and sharp, direct criticism. "
        "You are not afraid to explicitly name those responsible, including the ruling BJP, "
        "Prime Minister Narendra Modi, or specific union/state ministers. "
        "Your tone is authoritative, analytical, and brutally honest, combining hard statistics with "
        "deep empathy for the common Indian citizen. You write in clear, impactful English. "
        "\n\nWhen given a news story, return ONLY a JSON object with these keys: "
        '{"twitter_post": "...", "instagram_post": "...", "image_prompt": "..."}'
        "\n\ntwitter_post rules:"
        "\n- Since you have X Premium, you are NOT bound by character limits. "
        "\n- Write a devastating, long-form analytical post (3-4 paragraphs). "
        "\n- Paragraph 1: The Hook. Start with a shocking, hard-hitting summary of the failure. Name the politicians or party. "
        "\n- Paragraph 2: The Data. Present the hard statistics, money lost, or numbers of people affected. "
        "\n- Paragraph 3: The Accountability. Ask sharp, direct questions of the leadership (e.g., 'If the PM promised X, why is Y happening?'). "
        "\n- End with a strong call-to-action and 4-6 highly relevant hashtags."
        "\n\ninstagram_post rules:"
        "\n- Adapt the Twitter post into an emotionally resonant, storytelling format suitable for Instagram. "
        "End with a powerful citizen call-to-action. 6-8 hashtags."
        "\n\nimage_prompt rules:"
        "\n- Write a prompt for generating a clever, hand-drawn style editorial political cartoon."
        "\n- Style: Indian newspaper political cartoon, watercolor and ink caricature style, similar to R.K. Laxman or Satish Acharya."
        "\n- CRITICAL RULE TO AVOID AI BANS: Do NOT mention real political figures' true names (use generic terms like 'politician' or 'leader')."
        "\n- CRITICAL RULE FOR TEXT: DO NOT INCLUDE ANY WORDS, LABELS, OR SPEECH BUBBLES IN THE IMAGE. The metaphor must be entirely visual."
        "\n- Focus on witty visual metaphors: e.g., 'A fat politician sitting on a shrinking piece of land while ordinary citizens swim in water', "
        "'A tiny common man carrying a massive boulder shaped like a percentage sign on his back, representing inflation'."
        "\n- The image should look like a high-quality hand-drawn newspaper cartoon with a clean, minimalist background."
    )

    user_message = (
        f"News Headline: {news_data.get('headline', 'N/A')}\n"
        f"Summary: {news_data.get('summary', 'N/A')}\n"
        f"Key Fact: {news_data.get('key_fact', 'N/A')}\n"
        f"Politicians Involved: {news_data.get('politicians_involved', 'N/A')}\n"
        f"People Affected: {news_data.get('affected_people', 'N/A')}\n"
        f"Source: {news_data.get('source', 'N/A')}"
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1200,
        temperature=0.85,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content.strip())
    print(f"  → Post generated ✅ (Keys found: {list(result.keys())})")
    
    # Failsafe: if image_prompt is missing or empty, provide a default
    if not result.get("image_prompt"):
        print("  ⚠️ Warning: GPT-4o returned empty image_prompt. Supplying failsafe prompt.")
        result["image_prompt"] = "A clever, hand-drawn Indian newspaper political cartoon showing a giant politician ignoring a struggling common man. Watercolor caricature style, no text or words."
        
    return result


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: GENERATE IMAGE via Fal AI (Flux 1.1 Pro)
# ═══════════════════════════════════════════════════════════════════════════
def generate_image(image_prompt: str, output_dir: Path) -> Path:
    """
    Generates a high-quality image using Fal AI's Flux 1.1 Pro model.
    Returns the local path to the saved image.
    """
    print("[3/3] 🎨 Generating image with Flux 1.1 Pro (via Fal AI)...")

    # fal_client automatically reads the FAL_KEY environment variable.
    os.environ["FAL_KEY"] = os.getenv("FAL_KEY")

    try:
        result = fal_client.subscribe(
            "fal-ai/flux-pro/v1.1",
            arguments={
                "prompt": image_prompt,
                "image_size": "square_hd",
            },
            with_logs=True
        )
        
        img_url = result['images'][0]['url']
        
        # Download the image
        img_bytes = requests.get(img_url, timeout=30).content
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path  = output_dir / f"post_image_{timestamp}.jpg"
        img_path.write_bytes(img_bytes)
        print(f"  → Image saved: {img_path} ✅")
        return img_path
    except Exception as e:
        print(f"  ❌ Image Generation Error: {e}")
        # Fallback to a blank image or raise to crash and trigger Telegram failure handling.
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
📰 SOURCE NEWS
━━━━━━━━━━━━━━━━━━━━━━
Headline : {news_data.get('headline', 'N/A')}
Summary  : {news_data.get('summary', 'N/A')}
Key Fact : {news_data.get('key_fact', 'N/A')}
Affected : {news_data.get('affected_people', 'N/A')}
Source   : {news_data.get('source', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━
🐦 TWITTER POST
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
                    action = data.split("_")[0]   # 'approve', 'regen', or 'skip'
                    # Instant pop-up acknowledgment on the button
                    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
                        "callback_query_id": cb["id"],
                        "text": {"approve": "✅ Approved!",
                                 "regen":   "🔄 Regenerating...",
                                 "skip":    "⏭️ Skipped"}.get(action, "Got it!"),
                        "show_alert": False,
                    }, timeout=5)
                    # Confirmation message in chat
                    action_label = {"approve": "✅ Approved! Post scheduled.",
                                    "regen":   "🔄 Regenerating a new post...",
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

    # 1. Send the news context
    send_telegram_message(
        f"🇮🇳 <b>NEW POST DRAFT READY</b>\n\n"
        f"📰 <b>News:</b> {headline}\n"
        f"📊 <b>Key Fact:</b> {news_data.get('key_fact', 'N/A')}"
    )

    # 2. Send the generated image (no caption to avoid length limits)
    send_telegram_photo(img_path, caption="(Image generated for this post)")

    # 3. Send the long-form Twitter post
    twitter_post = post_data.get("twitter_post", "")
    send_telegram_message(f"🐦 <b>Twitter:</b>\n\n{twitter_post}")

    # 4. Send the Instagram post
    ig_post = post_data.get("instagram_post", "")
    send_telegram_message(f"📸 <b>Instagram:</b>\n\n{ig_post}")

    # 5. Send approval buttons
    send_telegram_approval_prompt(draft_id)

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

    # Step 1: Fetch News
    news_data = fetch_latest_news()

    # Step 2: Generate Post Text
    post_data = generate_post_text(news_data)

    # Step 3: Generate Image (gpt-image-1)
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
        print("  🔄  REGENERATE requested — Re-running pipeline...")
        run_pipeline()         # Recursively run again
        return
    else:
        print("  ⏭️  POST SKIPPED.")

    print(f"  📄  Draft: {draft_file}")
    print(f"  🖼️   Image: {img_path}")
    print("═"*60 + "\n")


if __name__ == "__main__":
    run_pipeline()
