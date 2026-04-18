"""Drafts single Twitter replies in the Weary Insider voice.

Supersedes the Grok-based engagement_agent.py. Loads persona from
config/agents.yaml, enforces CLAUDE.md style rules, and runs a regex
rejector on the output before returning."""

import os
import re
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent
AGENTS_YAML = REPO_ROOT / "config" / "agents.yaml"

MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS = "claude-opus-4-7"
MAX_REPLY_CHARS = 270

# Regex rejector patterns — any hit means regenerate.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F000-\U0001F2FF"
    "]",
    flags=re.UNICODE,
)
_HASHTAG_RE = re.compile(r"(?:^|\s)#\w+")
_INSULT_RE = re.compile(
    r"\b(you\s+are\s+(?:a|an)\s+\w+|shut\s+up|idiot|fool|moron|stupid|retard)\b",
    flags=re.IGNORECASE,
)
_BANNED_PHRASES = [
    "picture this",
    "imagine this",
    "let's talk about",
    "buckle up",
    "dive in",
    "shocking turn",
    "in today's world",
]


@dataclass
class ReplyDraft:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


class ReplyRejected(Exception):
    """Raised when a draft fails validation."""


def _load_persona() -> str:
    with open(AGENTS_YAML, encoding="utf-8") as f:
        agents = yaml.safe_load(f)
    g = agents["ghostwriter_agent"]
    return f"{g['backstory'].strip()}\n\nWriting goal: {g['goal'].strip()}"


_PERSONA = _load_persona()

_STYLE_RULES = """
STYLE RULES (non-negotiable):
- NO hashtags (#). The algorithm penalizes them.
- NO emojis of any kind.
- Single-sentence lines, separated by a blank line. A reply is usually 1-3 lines.
- Launch directly into the critique. No "picture this", "imagine", "let's talk about", "buckle up".
- Name the politician or ministry responsible when the target tweet implicates one.
- Simple vocabulary. Punchy. Desi sarcasm welcome, Hinglish analogies welcome.
- Never insult the target author personally. Attack the claim, the record, the policy — not the person.
- Back the claim with a concrete fact (year, number, name, broken promise) when possible.
- HARD LIMIT: 270 characters total. If you can't fit it, cut the weakest clause.
- Output ONLY the reply text. No preamble, no quotes, no explanations.
""".strip()


def _build_system_prompt(campaign_stance: Optional[str]) -> list:
    """Returns a system prompt list shaped for prompt caching.

    The persona + style block is cache-breakpoint'd; the per-call
    campaign stance is appended uncached."""
    blocks = [
        {
            "type": "text",
            "text": f"{_PERSONA}\n\n{_STYLE_RULES}",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if campaign_stance:
        blocks.append({"type": "text", "text": f"CAMPAIGN STANCE: {campaign_stance}"})
    return blocks


def _validate(text: str) -> None:
    if not text:
        raise ReplyRejected("empty draft")
    if len(text) > MAX_REPLY_CHARS:
        raise ReplyRejected(f"too long: {len(text)} chars")
    if _EMOJI_RE.search(text):
        raise ReplyRejected("contains emoji")
    if _HASHTAG_RE.search(text):
        raise ReplyRejected("contains hashtag")
    if _INSULT_RE.search(text):
        raise ReplyRejected("contains personal insult")
    low = text.lower()
    for phrase in _BANNED_PHRASES:
        if phrase in low:
            raise ReplyRejected(f"banned phrase: {phrase}")


def _strip_output(text: str) -> str:
    text = text.strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    return text


def generate(
    target_text: str,
    target_author: str,
    source: str,
    campaign_stance: Optional[str] = None,
    model: str = MODEL_SONNET,
) -> ReplyDraft:
    """Draft a single reply. Raises ReplyRejected on validation failure."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    system_blocks = _build_system_prompt(campaign_stance)

    user_msg = (
        f"Source: {source}\n"
        f"Target author: @{target_author}\n"
        f"Target tweet:\n\"\"\"\n{target_text}\n\"\"\"\n\n"
        "Draft the reply now. 270 characters maximum. Output only the reply text."
    )

    resp = client.messages.create(
        model=model,
        max_tokens=400,
        system=system_blocks,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = "".join(b.text for b in resp.content if b.type == "text")
    text = _strip_output(raw)
    _validate(text)

    return ReplyDraft(
        text=text,
        model=model,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


def generate_with_retry(
    target_text: str,
    target_author: str,
    source: str,
    campaign_stance: Optional[str] = None,
) -> ReplyDraft:
    """One Sonnet attempt, one Opus retry on rejection. Raises if both fail."""
    try:
        return generate(target_text, target_author, source, campaign_stance, MODEL_SONNET)
    except ReplyRejected as first:
        try:
            return generate(target_text, target_author, source, campaign_stance, MODEL_OPUS)
        except ReplyRejected as second:
            raise ReplyRejected(f"sonnet: {first}; opus: {second}")


if __name__ == "__main__":
    sample = (
        "Under the visionary leadership of PM Modi, India has become the fastest "
        "growing major economy. Har Ghar Tiranga, Sabka Saath Sabka Vikas!"
    )
    draft = generate_with_retry(sample, "bjp4india", source="bjp")
    print(draft)
