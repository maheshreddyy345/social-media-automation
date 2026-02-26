import yaml
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from models.post import CurationResult, ThreadResult
from tools.scraper_tool import scrape_critical_tweets
from tools.forensics_tool import search_and_download_forensics, verify_fact_via_web
from tools.research_tool import perplexity_deep_research
import os
from dotenv import load_dotenv

load_dotenv()

# Force CrewAI and LangChain to natively route ALL "OpenAI" traffic to xAI
os.environ["OPENAI_API_KEY"] = os.getenv("XAI_API_KEY")
os.environ["OPENAI_BASE_URL"] = "https://api.x.ai/v1"

llm = ChatOpenAI(
    model="grok-3",
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

class AccountabilityCrew:
    def __init__(self):
        with open('config/agents.yaml', 'r') as f:
            self.agents_config = yaml.safe_load(f)
        with open('config/tasks.yaml', 'r') as f:
            self.tasks_config = yaml.safe_load(f)
            
    # --- AGENTS ---
    def intelligence_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['intelligence_agent'],
            llm=llm,
            verbose=True,
            memory=False,
            tools=[scrape_critical_tweets]
        )
        
    def editor_in_chief_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['editor_in_chief_agent'],
            llm=llm,
            verbose=True
        )

    def media_forensics_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['media_forensics_agent'],
            llm=llm,
            verbose=True,
            tools=[search_and_download_forensics, verify_fact_via_web]
        )

    def deep_researcher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['deep_researcher_agent'],
            llm=llm,
            verbose=True,
            tools=[perplexity_deep_research]
        )

    def framing_strategist_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['framing_strategist_agent'],
            llm=llm,
            verbose=True
        )

    def ghostwriter_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['ghostwriter_agent'],
            llm=llm,
            verbose=True
        )

    def thread_architect_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['thread_architect_agent'],
            llm=llm,
            verbose=True
        )

    # --- TASKS ---
    def gather_intelligence_task(self) -> Task:
        return Task(
            config=self.tasks_config['gather_intelligence'],
            agent=self.intelligence_agent()
        )

    def curate_top_story_task(self) -> Task:
        return Task(
            config=self.tasks_config['curate_top_story'],
            agent=self.editor_in_chief_agent(),
            output_pydantic=CurationResult
        )

    def fetch_forensic_media_task(self) -> Task:
        return Task(
            config=self.tasks_config['fetch_forensic_media'],
            agent=self.media_forensics_agent()
        )

    def deep_dive_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['deep_dive_research_task'],
            agent=self.deep_researcher_agent()
        )

    def develop_framing_strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config['develop_framing_strategy_task'],
            agent=self.framing_strategist_agent()
        )

    def write_thread_draft_task(self) -> Task:
        return Task(
            config=self.tasks_config['write_thread_draft'],
            agent=self.ghostwriter_agent()
        )

    def split_into_thread_task(self) -> Task:
        return Task(
            config=self.tasks_config['split_into_thread'],
            agent=self.thread_architect_agent(),
            output_pydantic=ThreadResult
        )

    # --- THE CREW ---
    def run(self):
        crew = Crew(
            agents=[
                self.intelligence_agent(),
                self.editor_in_chief_agent(),
                self.media_forensics_agent(),
                self.deep_researcher_agent(),
                self.framing_strategist_agent(),
                self.ghostwriter_agent(),
                self.thread_architect_agent()
            ],
            tasks=[
                self.gather_intelligence_task(),
                self.curate_top_story_task(),
                self.fetch_forensic_media_task(),
                self.deep_dive_research_task(),
                self.develop_framing_strategy_task(),
                self.write_thread_draft_task(),
                self.split_into_thread_task()
            ],
            process=Process.sequential,
            verbose=True
        )
        result = crew.kickoff()
        return result

if __name__ == "__main__":
    crew = AccountabilityCrew()
    print("Starting Crew Execution...")
    final_output = crew.run()
    print("FINISHED:\n", final_output)
