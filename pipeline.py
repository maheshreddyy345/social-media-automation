"""Claude Agent SDK pipeline orchestrator for Cold Open.

Replaces the sequential CrewAI crew with a parallel-capable pipeline
using Claude subagents. The orchestrator (Opus) manages the flow:

  Scrape → Curate → [Forensics || Research] → Frame+Write → [Split || ImageGen] → Merge

Usage:
    from pipeline import run_pipeline
    thread_result = asyncio.run(run_pipeline())
"""
import asyncio
import json
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, ResultMessage
from models.post import ThreadResult
from tools.sdk_tools import tools_server
from prompts import (
    CURATOR_PROMPT,
    FORENSICS_PROMPT,
    RESEARCHER_PROMPT,
    FRAMER_WRITER_PROMPT,
    THREAD_ARCHITECT_PROMPT,
    IMAGE_GENERATOR_PROMPT,
    ORCHESTRATOR_PROMPT,
)


# --- Subagent definitions ---

AGENTS = {
    "curator": AgentDefinition(
        description="Score raw tweets 1-10 and select the single most devastating story. Returns CurationResult JSON.",
        prompt=CURATOR_PROMPT,
        model="opus",
    ),
    "forensics": AgentDefinition(
        description="Search for supplementary media (politician portraits, official documents) via DuckDuckGo and download to drafts/.",
        prompt=FORENSICS_PROMPT,
        tools=[
            "mcp__cold-open-tools__search_and_download_forensics",
            "mcp__cold-open-tools__verify_fact_via_web",
        ],
        model="sonnet",
    ),
    "researcher": AgentDefinition(
        description="Run deep background research via Perplexity API on the selected story. Returns a detailed briefing.",
        prompt=RESEARCHER_PROMPT,
        tools=["mcp__cold-open-tools__perplexity_deep_research"],
        model="opus",
    ),
    "framer-writer": AgentDefinition(
        description="Develop the narrative framing angle and write the full thread draft. No emojis, no hashtags, single-sentence lines.",
        prompt=FRAMER_WRITER_PROMPT,
        model="opus",
    ),
    "thread-architect": AgentDefinition(
        description="Split a long draft into 1-3 long-form tweets (up to 4000 chars each). Returns ThreadResult JSON.",
        prompt=THREAD_ARCHITECT_PROMPT,
        model="sonnet",
    ),
    "image-generator": AgentDefinition(
        description="Generate an editorial image prompt from the draft and create the image via Nano Banana 2.",
        prompt=IMAGE_GENERATOR_PROMPT,
        tools=["mcp__cold-open-tools__generate_nano_banana_image"],
        model="sonnet",
    ),
}


async def run_pipeline() -> ThreadResult:
    """Execute the full Cold Open pipeline with parallel subagents.

    Returns a validated ThreadResult with tweets and media_path.
    """
    options = ClaudeAgentOptions(
        allowed_tools=[
            "Agent",
            "mcp__cold-open-tools__scrape_critical_tweets",
        ],
        mcp_servers={"cold-open-tools": tools_server},
        agents=AGENTS,
        model="opus",
        system_prompt=ORCHESTRATOR_PROMPT,
        output_format={
            "type": "json_schema",
            "schema": ThreadResult.model_json_schema(),
        },
    )

    async for message in query(
        prompt=(
            "Execute the full Cold Open pipeline now. "
            "Scrape → Curate → Research+Forensics (parallel) → Frame+Write → Split+Image (parallel) → Return ThreadResult."
        ),
        options=options,
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            return ThreadResult.model_validate(message.structured_output)

    raise RuntimeError("Pipeline did not return a successful result.")


if __name__ == "__main__":
    result = asyncio.run(run_pipeline())
    print("\n=== PIPELINE RESULT ===")
    print(f"Tweets: {len(result.tweets)}")
    for i, tweet in enumerate(result.tweets, 1):
        print(f"\n--- Tweet {i} ---")
        print(tweet)
    print(f"\nMedia: {result.media_path}")
