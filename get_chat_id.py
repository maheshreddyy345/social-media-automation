"""
get_chat_id.py
───────────────
Run this script AFTER you have sent at least one message to your Telegram bot.
It will automatically detect your Chat ID and update the .env file for you.

Steps:
  1. Open Telegram
  2. Search for your bot (by name or username you gave it in BotFather)
  3. Tap the bot → tap START or just type "hello" and send it
  4. Come back and run:  .\\venv\\Scripts\\python.exe get_chat_id.py
"""

import requests
from pathlib import Path

BOT_TOKEN = "8730400920:AAFCJrx47iiUpJCTtzyuafIRoeeAavLVGKg"


def get_chat_id():
    print("🔍 Looking for messages sent to your bot...\n")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    r = requests.get(url, timeout=15)
    data = r.json()

    if not data.get("ok"):
        print("❌ Error calling Telegram API:", data)
        return

    updates = data.get("result", [])
    if not updates:
        print("⚠️  No messages found yet!")
        print("\n👉 Please do the following in Telegram:")
        print("   1. Open Telegram on your phone")
        print("   2. Search for your bot by its username")
        print("   3. Tap it → tap START button or type 'hello' and send")
        print("   4. Come back and run this script again")
        return

    # Get the chat_id from the most recent message or callback
    chat_id = None
    for update in updates:
        msg = update.get("message") or update.get("edited_message")
        if msg and "chat" in msg:
            chat_id = msg["chat"]["id"]
            username = msg["chat"].get("username", "")
            first_name = msg["chat"].get("first_name", "")
            print(f"✅ Found your chat!")
            print(f"   Name    : {first_name}")
            print(f"   Username: @{username}")
            print(f"   Chat ID : {chat_id}")
            break

    if not chat_id:
        print("⚠️  Could not extract Chat ID from updates.")
        print("Raw response:", data)
        return

    # Update .env file automatically
    env_path = Path(".env")
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        content = content.replace("your_telegram_chat_id_here", str(chat_id))
        env_path.write_text(content, encoding="utf-8")
        print(f"\n✅ .env file updated automatically with Chat ID: {chat_id}")
        print("You can now run main.py and the Telegram approval bot will work!")
    else:
        print(f"\n⚠️  .env file not found. Please manually add:")
        print(f"   TELEGRAM_CHAT_ID={chat_id}")


if __name__ == "__main__":
    get_chat_id()
