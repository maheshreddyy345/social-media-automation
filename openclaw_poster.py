"""Drives OpenClaw to post a drafted reply via the Twitter web UI.

OpenClaw runs as a local gateway (see openclaw.service). We shell out to
the CLI with an explicit instruction + a named session that holds the
logged-in Twitter cookies. On captcha/challenge detection the kill switch
is tripped so the scheduler stops until an operator re-logs in."""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from models.database import CandidateReply
from telegram_reply import send_plain

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
OPENCLAW_SESSION = os.getenv("OPENCLAW_SESSION_NAME", "twitter-main")
OPENCLAW_TIMEOUT_SEC = int(os.getenv("OPENCLAW_TIMEOUT_SEC", "180"))
OPENCLAW_THINKING = os.getenv("OPENCLAW_THINKING", "medium")
DRY_RUN = os.getenv("REPLY_BOT_DRY_RUN", "false").lower() in ("1", "true", "yes")
ENV_FILE = os.getenv("REPLY_BOT_ENV_FILE", ".env")

POSTED_URL_RE = re.compile(r"https?://(?:x|twitter)\.com/\w+/status/(\d+)")
CHALLENGE_MARKERS = (
    "captcha",
    "verify you are human",
    "unusual login",
    "confirm your identity",
    "log in to x",
    "sign up to x",
)


class PostFailed(Exception):
    pass


class ChallengeDetected(PostFailed):
    pass


def _build_prompt(candidate: CandidateReply) -> str:
    target_url = candidate.target_tweet_url
    reply_text = candidate.drafted_text or ""
    return (
        "Drive the logged-in Twitter/X web UI to post a reply.\n"
        "STEPS:\n"
        f"1. Navigate to: {target_url}\n"
        "2. Click the Reply button on THAT tweet (not a reply below it).\n"
        "3. In the compose box, type the exact text between the triple-angle markers, "
        "preserving line breaks and spacing. Do NOT add hashtags, emojis, or commentary.\n"
        f"<<<{reply_text}>>>\n"
        "4. Click the Post button.\n"
        "5. Wait until the posted reply appears in the thread.\n"
        "6. Return ONLY the permalink URL of the reply you just posted, on its own line.\n"
        "If at any point you see a captcha, 'verify you are human' challenge, unusual-login "
        "warning, or a login/signup wall, STOP and return the exact text: CHALLENGE_DETECTED"
    )


def _disable_kill_switch(reason: str) -> None:
    env_path = Path(ENV_FILE)
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith("REPLY_BOT_ENABLED="):
            lines[i] = "REPLY_BOT_ENABLED=false"
            found = True
            break
    if not found:
        lines.append("REPLY_BOT_ENABLED=false")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["REPLY_BOT_ENABLED"] = "false"
    send_plain(f"🛑 Reply bot DISABLED: {reason}. Re-login needed, then set REPLY_BOT_ENABLED=true.")


def _extract_posted_url(output: str) -> Optional[str]:
    # Walk lines from the end — the answer should be on the last non-empty line.
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        m = POSTED_URL_RE.search(line)
        if m:
            return m.group(0)
    return None


def _looks_like_challenge(output: str) -> bool:
    low = output.lower()
    if "challenge_detected" in low:
        return True
    return any(marker in low for marker in CHALLENGE_MARKERS)


def post_reply(candidate: CandidateReply) -> str:
    """Post via OpenClaw. Returns the posted reply URL. Raises PostFailed on error."""
    prompt = _build_prompt(candidate)

    if DRY_RUN:
        print(f"[openclaw] DRY RUN for #{candidate.id}. Would invoke:")
        print(f"  {OPENCLAW_BIN} agent --session {OPENCLAW_SESSION} --thinking {OPENCLAW_THINKING}")
        print(f"  prompt:\n{prompt}")
        return f"https://x.com/GetColdOpen/status/dryrun-{candidate.id}"

    cmd = [
        OPENCLAW_BIN,
        "agent",
        "--session", OPENCLAW_SESSION,
        "--thinking", OPENCLAW_THINKING,
        "--message", prompt,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=OPENCLAW_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        raise PostFailed(f"openclaw timed out after {OPENCLAW_TIMEOUT_SEC}s")

    output = (result.stdout or "") + "\n" + (result.stderr or "")

    if _looks_like_challenge(output):
        _disable_kill_switch("OpenClaw hit a challenge / login wall")
        raise ChallengeDetected("openclaw reported a challenge / login wall")

    if result.returncode != 0:
        raise PostFailed(f"openclaw exit {result.returncode}: {output[-400:]}")

    posted = _extract_posted_url(output)
    if not posted:
        raise PostFailed(f"could not parse posted URL from openclaw output: {output[-400:]}")
    return posted
