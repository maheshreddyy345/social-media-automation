import os
import time
import requests
import re
from dotenv import load_dotenv
from main import publish_thread_to_twitter
from models.post import ThreadResult
from models.database import init_db, SessionLocal, ContentLog, CandidateReply

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def get_latest_draft_from_db():
    try:
        init_db()
        db = SessionLocal()
        log = db.query(ContentLog).order_by(ContentLog.id.desc()).first()
        db.close()
        if log and log.drafted_thread:
            import json
            tweets = json.loads(log.drafted_thread)
            media = log.media_paths if log.media_paths else ""
            return ThreadResult(tweets=tweets, media_path=media)
    except Exception as e:
        print(f"Error fetching from DB: {e}")
    return None

def extract_tweets_from_message(text):
        # Fallback if DB is unavailable. Extract from Telegram message text.
        tweets = []
        parts = re.split(r'Tweet \d+:', text)
        for part in parts[1:]:
             clean_tweet = part.strip()
             if clean_tweet:
                 tweets.append(clean_tweet)
        return ThreadResult(tweets=tweets)

def handle_reply_callback(data, chat_id, message_id, message):
    """Dispatch for the reply-bot callbacks. Status flips only — the
    reply_scheduler's post_tick() picks up 'approved' rows and posts via OpenClaw."""
    action, _, id_str = data.partition(":")
    try:
        cid = int(id_str)
    except ValueError:
        return

    db = SessionLocal()
    try:
        row = db.query(CandidateReply).get(cid)
        if not row:
            _edit(chat_id, message_id, (message.get('text', '') or '') + "\n\n❌ <b>Row not found.</b>")
            return

        original = message.get('text', '') or ''

        if action == "reply_approve":
            if row.status != "pending_approval":
                _edit(chat_id, message_id, original + f"\n\n⚠️ <b>Already {row.status}.</b>")
                return
            row.status = "approved"
            db.commit()
            _edit(chat_id, message_id, original + "\n\n✅ <b>APPROVED — queued for OpenClaw post.</b>")
        elif action == "reply_regen":
            row.status = "pending_draft"
            row.drafted_text = None
            row.regen_count = (row.regen_count or 0) + 1
            db.commit()
            _edit(chat_id, message_id, original + "\n\n🔄 <b>Regenerating…</b>")
        elif action == "reply_skip":
            row.status = "skipped"
            db.commit()
            _edit(chat_id, message_id, original + "\n\n⏭️ <b>Skipped.</b>")
    finally:
        db.close()


def _edit(chat_id, message_id, text):
    requests.post(
        f"{TELEGRAM_API}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


def process_update(update):
    if 'callback_query' in update:
        query = update['callback_query']
        query_id = query['id']
        data = query['data']
        message = query['message']
        chat_id = message['chat']['id']
        message_id = message['message_id']
        
        # Acknowledge the callback immediately
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": query_id})

        if data.startswith("reply_approve:") or data.startswith("reply_regen:") or data.startswith("reply_skip:"):
            handle_reply_callback(data, chat_id, message_id, message)
            return

        if data == "approve":
            print(f"User approved message_id {message_id}")
            
            # Fetch the actual tweets
            thread_result = get_latest_draft_from_db()
            if not thread_result or not thread_result.tweets:
                 print("DB fetch failed, parsing message text...")
                 thread_result = extract_tweets_from_message(message.get('text', ''))
            
            if thread_result and thread_result.tweets:
                try:
                    publish_thread_to_twitter(thread_result)
                    
                    # Update message to remove buttons and show success
                    success_text = message.get('text', '') + "\n\n✅ <b>APPROVED & PUBLISHED TO X / TWITTER!</b>"
                    requests.post(f"{TELEGRAM_API}/editMessageText", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": success_text,
                        "parse_mode": "HTML"
                    })
                except Exception as e:
                    print(f"Publish failed: {e}")
                    requests.post(f"{TELEGRAM_API}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": f"❌ Failed to publish: {e}"
                    })
            else:
                requests.post(f"{TELEGRAM_API}/sendMessage", json={
                     "chat_id": chat_id,
                     "text": "❌ Could not extract tweets to publish."
                })
                
        elif data == "regenerate":
            print(f"User requested regeneration for message_id {message_id}")
            requests.post(f"{TELEGRAM_API}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": message.get('text', '') + "\n\n🔄 <b>Regeneration Requested. The cron job will re-run later, or you can trigger manually.</b>",
                "parse_mode": "HTML"
            })
            
        elif data == "skip":
            print(f"User skipped message_id {message_id}")
            requests.post(f"{TELEGRAM_API}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": message.get('text', '') + "\n\n⏭️ <b>Story Skipped.</b>",
                "parse_mode": "HTML"
            })

def main():
    print("🤖 Telegram Polling Listener Started...")
    offset = None
    
    while True:
        try:
            url = f"{TELEGRAM_API}/getUpdates"
            params = {"timeout": 10}
            if offset:
                params["offset"] = offset
                
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for update in data["result"]:
                        process_update(update)
                        offset = update["update_id"] + 1
            else:
                 print(f"Error fetching updates: {response.status_code}")
                 
        except Exception as e:
            print(f"Polling error: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    main()
