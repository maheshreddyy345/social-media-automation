"""Telegram card for a single candidate reply.

Sent by reply_scheduler.py after drafting. The three callback_data values
(reply_approve:<id>, reply_regen:<id>, reply_skip:<id>) are handled in
telegram_listener.py."""

import os
import html
import requests
from dotenv import load_dotenv

from models.database import CandidateReply

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _format_card(c: CandidateReply) -> str:
    target_preview = (c.target_text or "")[:220]
    if c.target_text and len(c.target_text) > 220:
        target_preview += "…"
    camp = f" · <b>{html.escape(c.campaign_name)}</b>" if c.campaign_name else ""
    return (
        f"🎯 <b>Reply candidate #{c.id}</b> · <i>{c.source}</i>{camp}\n"
        f"<b>Target:</b> @{html.escape(c.target_author)}\n"
        f"<a href=\"{c.target_tweet_url}\">{html.escape(c.target_tweet_url)}</a>\n\n"
        f"<i>{html.escape(target_preview)}</i>\n\n"
        f"<b>Draft:</b>\n"
        f"{html.escape(c.drafted_text or '')}"
    )


def send_reply_candidate(candidate: CandidateReply) -> dict:
    """POST the candidate card with Approve/Regen/Skip buttons. Returns Telegram response JSON."""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve & Post", "callback_data": f"reply_approve:{candidate.id}"},
                {"text": "🔄 Regen", "callback_data": f"reply_regen:{candidate.id}"},
            ],
            [
                {"text": "⏭️ Skip", "callback_data": f"reply_skip:{candidate.id}"},
            ],
        ]
    }
    resp = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": _format_card(candidate),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": keyboard,
        },
        timeout=15,
    )
    return resp.json()


def send_plain(text: str) -> None:
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
