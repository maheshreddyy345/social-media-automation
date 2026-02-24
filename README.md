# 🇮🇳 Political Accountability Engine

An automated social media pipeline that monitors Indian political news and generates sharp, data-driven commentary posts with editorial cartoon images.

## How It Works

1. **News Fetching** — Perplexity API (`sonar-pro`) finds the most impactful breaking news from the last 24-48 hours
2. **Text Generation** — GPT-4o drafts a long-form, analytical X/Twitter post with hard data and direct accountability questions
3. **Image Generation** — Flux 1.1 Pro (via Fal AI) creates a Satish Acharya-style editorial political cartoon
4. **Human Approval** — The draft is sent to Telegram for review (Approve / Regenerate / Skip)
5. **Publishing** — Approved posts are automatically published to X/Twitter via the API

## Tech Stack

| Component | Service |
|---|---|
| News Source | Perplexity API (sonar-pro) |
| Text Generation | OpenAI GPT-4o |
| Image Generation | Flux 1.1 Pro (Fal AI) |
| Approval UI | Telegram Bot |
| Publishing | Twitter/X API (OAuth 1.0a) |
| Hosting | GCP Compute Engine (e2-micro) |

## Setup

1. Clone this repo
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `source venv/bin/activate` (Linux) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in your API keys
6. Run: `python main.py`

## Environment Variables

Create a `.env` file with:

```
OPENAI_API_KEY=your_key
PERPLEXITY_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
TWITTER_CONSUMER_KEY=your_key
TWITTER_CONSUMER_SECRET=your_secret
TWITTER_ACCESS_TOKEN=your_token
TWITTER_ACCESS_TOKEN_SECRET=your_secret
FAL_KEY=your_fal_key
```

## Deployment (GCP)

The bot runs on a GCP `e2-micro` VM with a cron job every 6 hours:

```
0 */6 * * * cd /home/user/bot && /home/user/bot/venv/bin/python main.py >> /home/user/bot/logs/cron.log 2>&1
```

## License

Private — All rights reserved.
