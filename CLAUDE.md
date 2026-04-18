# Cold Open — Political Accountability Twitter Automation

Handle: `@GetColdOpen` (was `@Sawalkaro` prior to rebrand). Display name: "Cold Open". User ID: `2026024544314499072`.

## What This Project Does
Automates a Twitter/X account focused on Indian political accountability. User gives a topic, we research it, draft a thread, generate images, and post.

## Key APIs & Credentials
- **Twitter/X:** Tweepy V2 for `create_tweet`, V1.1 for `media_upload`. Credentials in `.env`
- **Image Generation:** Fal AI **Nano Banana 2** (`fal-ai/nano-banana-2`). Use 16:9, 2K, JPEG. `FAL_KEY` in `.env`
- **Web Research:** DuckDuckGo search (`duckduckgo_search` library) + WebSearch tool

## Thread Style Rules (NEVER BREAK)
- **NO hashtags** — algorithm penalizes them
- **NO emojis** — serious accountability account
- **Single-sentence lines** with blank lines between them
- **Max 3 long-form tweets** (up to 4000 chars each)
- **No storytelling intros** — no "Picture this", "Imagine", "Let's talk about"
- Simple vocabulary, punchy tone, name the politicians responsible

## Image Rules
- Use Nano Banana 2 (`fal-ai/nano-banana-2`) — NOT flux-pro
- Style: Subtle, editorial, photojournalistic
- No text in images, no real politician faces
- Always verify images visually with Read tool before posting

## Posting Pattern
```python
# V2 client for tweets, V1.1 api for media upload
client = tweepy.Client(consumer_key, consumer_secret, access_token, access_token_secret)
api = tweepy.API(tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret))

# Chain tweets via in_reply_to_tweet_id
# Attach images via api.media_upload() -> media_ids
```

## File Structure
- `main.py` — CrewAI pipeline entry point (automated mode)
- `crew.py` — Agent definitions
- `config/` — Agent and task YAML configs
- `tools/` — Scraper, research, forensics tools
- `models/` — Database ORM and Pydantic models
- `drafts/` — Temporary image storage (clean up after posting)
- `.claude/skills/` — Custom slash commands (`/post-thread`, `/trending-india`)

## Workflow
1. User gives topic OR runs `/trending-india` to find one
2. `/post-thread <topic>` researches, drafts, generates images
3. Show draft + images, wait for user approval
4. Post to Twitter, clean up drafts
