import os
import sys
import json
import re
import yaml
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from models.post import ThreadResult
from tools.research_tool import perplexity_deep_research
from tools.forensics_tool import search_and_download_forensics, verify_fact_via_web

load_dotenv()

# Force xAI routing
os.environ["OPENAI_API_KEY"] = os.getenv("XAI_API_KEY")
os.environ["OPENAI_BASE_URL"] = "https://api.x.ai/v1"

llm = ChatOpenAI(
    model="grok-3",
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

def test_custom_article(headline: str, url: str):
    with open('config/agents.yaml', 'r') as f:
        agents_config = yaml.safe_load(f)
    with open('config/tasks.yaml', 'r') as f:
        tasks_config = yaml.safe_load(f)
        
    print(f"[START] Injecting custom article: {headline}")
    
    # Init Sub-Agents
    editor = Agent(config=agents_config['editor_in_chief_agent'], llm=llm, verbose=False)
    forensics = Agent(config=agents_config['media_forensics_agent'], llm=llm, tools=[search_and_download_forensics, verify_fact_via_web], verbose=False)
    researcher = Agent(config=agents_config['deep_researcher_agent'], llm=llm, tools=[perplexity_deep_research], verbose=False)
    framer = Agent(config=agents_config['framing_strategist_agent'], llm=llm, verbose=False)
    ghostwriter = Agent(config=agents_config['ghostwriter_agent'], llm=llm, verbose=False)
    architect = Agent(config=agents_config['thread_architect_agent'], llm=llm, verbose=False)

    # Custom Start Task
    editor_task = Task(
        description=f"Analyze this raw news: '{headline}' at URL: {url}. Extract the 'headline', 'key_fact', and explicitly identify the 'primary_politician_involved' to blame.",
        expected_output="A JSON object containing the headline, key_fact, url, and primary_politician_involved.",
        agent=editor
    )
    
    forensic_task = Task(config=tasks_config['fetch_forensic_media'], agent=forensics)
    
    research_task = Task(
        description=f"Original News Headline: '{headline}'\nArticle URL: {url}\n\nUsing the Perplexity Deep Research tool, run an extensive background check on this situation. Look for the history of the project, previous contractor failures, related political statements, and similar past incidents.",
        expected_output="A detailed research briefing containing historical context, names, and related failures to empower the framing strategy.",
        agent=researcher
    )
    
    framing_task = Task(config=tasks_config['develop_framing_strategy_task'], agent=framer)
    write_task = Task(config=tasks_config['write_thread_draft'], agent=ghostwriter)
    split_task = Task(config=tasks_config['split_into_thread'], agent=architect, output_pydantic=ThreadResult)

    crew = Crew(
        agents=[editor, forensics, researcher, framer, ghostwriter, architect],
        tasks=[editor_task, forensic_task, research_task, framing_task, write_task, split_task],
        process=Process.sequential,
        verbose=False
    )
    
    result = crew.kickoff()
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: python test_custom_article.py "Headline text" "https://article-url.com"')
    else:
        headline = sys.argv[1]
        url = sys.argv[2]
        res = test_custom_article(headline, url)
        
        # Send to Telegram
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
        
        def send_telegram_message(text: str, media_path: str = None):
            import requests
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Approve & Schedule", "callback_data": "approve"},
                        {"text": "🔄 Regenerate", "callback_data": "regenerate"}
                    ],
                    [
                        {"text": "⏭️ Skip", "callback_data": "skip"}
                    ]
                ]
            }
            if media_path and os.path.exists(media_path):
                print(f"Sending Photo to Telegram: {media_path}")
                try:
                    with open(media_path, "rb") as photo:
                        requests.post(f"{TELEGRAM_API}/sendPhoto", data={"chat_id": TELEGRAM_CHAT_ID}, files={"photo": photo}, timeout=25)
                except Exception as e:
                    print(f"Failed to send photo: {e}")
                    
            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": keyboard
            }, timeout=15)

        import ast
        thread_data = {"tweets": []}
        raw_text = str(res)
        
        # 1. Try native parsing
        if hasattr(res, 'json_dict') and res.json_dict:
             thread_data = res.json_dict
        else:
             # 2. Try raw JSON extraction
             try:
                 clean = re.sub(r"^```json\s*|```$", "", raw_text, flags=re.MULTILINE).strip()
                 thread_data = json.loads(clean)
             except Exception:
                 # 3. Try Python variable extraction (tweets=[...])
                 t_match = re.search(r'tweets\s*=\s*(\[.*?\])', raw_text, re.DOTALL)
                 if t_match:
                     try:
                         thread_data["tweets"] = ast.literal_eval(t_match.group(1))
                     except Exception:
                         pass
                 m_match = re.search(r"media_path\s*=\s*['\"]([^'\"]+)['\"]", raw_text)
                 if m_match:
                     thread_data["media_path"] = m_match.group(1)
                     
        if not thread_data.get("tweets"):
             thread_data["tweets"] = [raw_text]
            
        if thread_data and "tweets" in thread_data:
            message = f"🚨 <b>CUSTOM ARTICLE DRAFT</b> 🚨\n{headline}\n\n"
            
            def escape_tg(t):
                return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
            for i, tweet in enumerate(thread_data["tweets"]):
                safe_tweet = escape_tg(tweet)
                message += f"<b>Tweet {i+1}:</b>\n{safe_tweet}\n\n"
            
            print("Writing locally to latest_draft.md as a fallback...")
            with open("latest_draft.md", "w", encoding="utf-8") as f:
                 f.write(message)
                 
            media_path = thread_data.get("media_path")
            print("Sending to Telegram...")
            if len(message) > 4000:
                 chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                 for c_idx, chunk in enumerate(chunks):
                     if c_idx == 0:
                         send_telegram_message(chunk, media_path)
                     else:
                         send_telegram_message(chunk)
            else:
                 send_telegram_message(message, media_path)
            print("Sent successfully!")
        else:
            print("Formatting failed.")
