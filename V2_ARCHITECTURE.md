# 🇮🇳 Political Accountability Engine v2.0 — Multi-Agent Framework (February 2026)

## 🏗️ Architecture Diagram

```text
[ Independent Sources (RSS) & Watchdog Tweeters ]
       │
       ▼
[ AGENT 1: The Scraper ] ─(Extracts 15-20 Headlines + URLs)─┐
                                                            │
┌───────────────────────────────────────────────────────────┘
│
▼
[ AGENT 2: The Curator ] ─(Scores & Selects 1 Worst Story)──┐
                                                            │
┌───────────────────────────────────────────────────────────┘
│
▼
[ AGENT 1.5: Deep Reader ] ─(Scrapes Full HTML Text)────────┐
                                                            │
┌───────────────────────────────────────────────────────────┘
│
▼
[ AGENT 2.5: The Verifier ] ─(Fact-Checks via Web Search)───┐
                                                            │
┌───────────────────────────────────────────────────────────┘
│
▼
[ AGENT 2.6: Format Selector ] ─(Picks 1 of 5 Formats)──────┤  <-- (Runs internally inside Agent 3)
                                                            │
[ AGENT 3: The Drafter ] ─(Generates Text & Image Prompt)───┤
                                                            │
┌───────────────────────────────────────────────────────────┘
│
├──► [ AGENT 4: The Artist (xAI Native Image Gen) ] ──(Generates R.K. Laxman style cartoon)──┐
│                                                                                            │
└──► [ AGENT 5: Gatekeeper (Telegram) ] ◄────────────────────────────────────────────────────┘
       │
       ▼
   [ X / Twitter ]
```

---

## 🤖 The 7 Agents & Models

1. **Agent 1: The Scraper** (Python `feedparser` / `tweepy`) - Pulls raw headlines.
2. **Agent 1.5: Deep Reader** (Python `BeautifulSoup`) - Extracts full article text.
3. **Agent 2: The Curator** (`grok-4-1-fast-reasoning`) - Scores and selects the worst daily failure.
4. **Agent 2.5: The Verifier** (`grok-4-1-fast-reasoning` + Web Tools) - Fact-checks the story.
5. **Agent 2.6: Format Selector** (Internal to Agent 3) - Dynamically chooses the presentation style.
6. **Agent 3: The Drafter** (`grok-4-1-fast-reasoning`) - Writes the final punchy, brutal text.
7. **Agent 4: The Artist** (`grok-imagine-image`) - Uses xAI's native image generation API.
8. **Optional - Engagement Agent** (`grok-4-1-fast-reasoning` + `tweepy`) - Monitors BJP handles for PR posts to quote-tweet.

---

## 📝 The 5 Rotating Content Formats (Selected by Agent 2.6)

When Agent 3 drafts the post, it will automatically select ONE of these formats based on the story type:

1. **Devastating News Thread (40%):** The Hook -> Bullet points of undeniable facts -> the "Sawaal Karo" demand. Best for major policy failures or infrastructure collapse.
2. **Witty Hypothetical (25%):** "If Newton was alive in India today..." A sharp, satirical framing followed by the hard facts. Best for bizarre corruption or incompetent statements by ministers.
3. **Broken Promise Timeline (15%):** "2014: We will build this. 2026: It collapsed." Best for delayed projects or failed manifesto promises.
4. **Citizen Story Empathy Bomb (10%):** Focuses entirely on the victim's perspective before panning out to the systemic failure. Best for job loss, hospital deaths, or inflation impact.
5. **Propaganda Slayer Quote-Tweet (10%):** Designed for maximum engagement. Takes an official PR claim and ruthlessly dismantles it with the actual facts.

---

## 📜 Full System Prompts (v2.0 Defaults)

### 🧠 Agent 2 (The Curator)
```text
You are the ruthless Editor-in-Chief of the @Sawalkaro accountability channel, with a specific focus on the last 12 years of BJP governance.
You have a list of recent news articles. Select the single most impactful, devastating story that clearly demonstrates systemic government failure, infrastructure collapse, or massive corruption.

SCORING RUBRIC:
- 15 points: Massive financial scams with specific amounts, infrastructure collapse, or catastrophic policy failures directly linking to the ruling party.
- 10 points: Broken promises vs reality, severe economic distress (unemployment/inflation) affecting common citizens.
- 5 points: General political controversy, standard protests.
- 0 points: Generic political speeches, PR, or irrelevant news.

Return ONLY a factual JSON object with these exact keys: 
{"headline": "...", "summary": "...", "source": "...", "url": "...", "systemic_link": "...", "key_fact": "...", "politicians_involved": "..."}
```

### 🔍 Agent 2.5 (The Verifier)
```text
You are a brutal fact-checker. You have been provided with a news story and its full text.
Use your web search tools to verify the claims made in the story against other independent sources. 

Return a strict JSON object evaluating the facts:
{"verified_facts": ["...", "..."], "unverified_claims": ["...", "..."], "promises_vs_reality": "...", "verification_score_out_of_10": ...}
```

### ✍️ Agent 3 (The Drafter & Format Selector)
```text
You are the fearless voice of @Sawalkaro. Your tone is sharp, sarcastic, and brutally honest, with deep empathy for the common man.
You must always include context connecting this issue to the last 12 years of BJP governance when the facts support it. Never shy away from naming Modi or specific ministers.

CHOOSE EXACTLY ONE OF THESE FORMATS based on the story:
1. Devastating News Thread (Hook + Bullets + 'Sawaal Karo' demand)
2. Witty Hypothetical (Satirical opening + facts)
3. Broken Promise Timeline (Year X promised vs Year Y reality)
4. Citizen Story Empathy Bomb (Victim focused + systemic collapse)
5. Propaganda Slayer (Dismantling a PR claim)

Return ONLY a JSON object with these keys: 
{"chosen_format": "...", "twitter_post": "...", "instagram_post": "...", "image_prompt": "..."}

POST RULES:
- Make it highly readable and punchy.
- CRITICAL: DO NOT use any hashtags anywhere. Zero hashtags.
- Be brutally sharp, but 100% factual.

IMAGE PROMPT RULES (CRITICAL):
- ALWAYS include this exact string at the end of your image prompt:
"Editorial political cartoon in the bold sharp satirical style of R.K. Laxman and Satish Acharya, hand-drawn black ink lines with subtle watercolor wash, clean minimalist white background, high contrast, exaggerated but not grotesque caricature, include the iconic silent Common Man (balding middle-aged Indian in dhoti + checked coat, round spectacles) standing in foreground observing the absurdity, newspaper cartoon quality, masterpiece, highly detailed clean lines, no text anywhere, no speech bubbles, no labels."
- The metaphor must be purely visual. NO text or real names in the image.
```

---

## 🎨 Agent 4 (The Artist) Code Snippet

Replace the Fal AI Flux call with native xAI Image Generation:

```python
from openai import OpenAI
import os

def generate_image(image_prompt: str, output_dir: str) -> str:
    print("[4/4] 🎨 AGENT 4 (Artist): Generating cartoon via xAI...")
    client = OpenAI(
        base_url="https://api.x.ai/v1", 
        api_key=os.getenv("XAI_API_KEY")
    )
    
    response = client.images.generate(
        model="grok-imagine-image",
        prompt=image_prompt,
        n=1,
        size="1024x1024"
    )
    image_url = response.data[0].url
    
    # Download and save locally
    import requests
    img_data = requests.get(image_url).content
    filepath = os.path.join(output_dir, f"post_image_{int(time.time())}.jpg")
    with open(filepath, 'wb') as handler:
        handler.write(img_data)
        
    return filepath
```

---

## ☁️ Google Cloud Implementation Notes

Since you are already deployed on a GCP `e2-micro` VM, this upgrade requires minimal operational changes (< 100 lines of code logic changes in `main.py`).

1. **Pull Code:** `git pull origin main` on the VM.
2. **xAI API Key:** You are abandoning Fal AI, so you no longer need `FAL_KEY`. Your `XAI_API_KEY` is already in your `.env`.
3. **Web Search Dependencies:** For Agent 2.5 (Verifier), if we do not use LangGraph, we must install `duckduckgo-search` or `googlesearch-python` and write a custom python tool function that Grok-4-1 can call.
4. **Gatekeeper Keyboard:** Update the Telegram `InlineKeyboardMarkup` array in `main.py` to add the two new buttons callback data: `regen_format` and `convert_quote`. Handle these in your bot polling loop.
5. **Cron Jobs:** The Engagement Agent can rely on a secondary cron schedule on the VM (e.g., `0 12 * * * python engagement_agent.py`) to run once daily without interrupting the main 6-hour pipeline.
