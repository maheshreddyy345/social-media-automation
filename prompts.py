"""Prompt builder for Claude Agent SDK subagents.

Loads agent roles/backstories from config/agents.yaml and task descriptions
from config/tasks.yaml, then builds system prompts for each subagent.
"""
import yaml
from pathlib import Path

_config_dir = Path(__file__).parent / "config"

with open(_config_dir / "agents.yaml", "r") as f:
    AGENTS_CONFIG = yaml.safe_load(f)

with open(_config_dir / "tasks.yaml", "r") as f:
    TASKS_CONFIG = yaml.safe_load(f)


def _build_prompt(agent_key: str, task_keys: list[str]) -> str:
    """Build a system prompt from agent config + one or more task configs."""
    agent = AGENTS_CONFIG[agent_key]
    lines = [
        f"ROLE: {agent['role'].strip()}",
        f"GOAL: {agent['goal'].strip()}",
        "",
        "BACKSTORY:",
        agent["backstory"].strip(),
        "",
        "YOUR TASK:",
    ]
    for tk in task_keys:
        task = TASKS_CONFIG[tk]
        lines.append(task["description"].strip())
        lines.append("")
        lines.append(f"EXPECTED OUTPUT: {task['expected_output'].strip()}")
    return "\n".join(lines)


# --- Individual subagent prompts ---

CURATOR_PROMPT = _build_prompt(
    "editor_in_chief_agent",
    ["curate_top_story"],
)

FORENSICS_PROMPT = _build_prompt(
    "media_forensics_agent",
    ["fetch_forensic_media"],
)

RESEARCHER_PROMPT = _build_prompt(
    "deep_researcher_agent",
    ["deep_dive_research_task"],
)

# Merged: Framing Strategist + Ghostwriter into one subagent
FRAMER_WRITER_PROMPT = (
    _build_prompt("framing_strategist_agent", ["develop_framing_strategy_task"])
    + "\n\n--- PHASE 2: WRITING ---\n\n"
    + _build_prompt("ghostwriter_agent", ["write_thread_draft"])
)

THREAD_ARCHITECT_PROMPT = _build_prompt(
    "thread_architect_agent",
    ["split_into_thread"],
)

IMAGE_GENERATOR_PROMPT = """ROLE: Editorial Image Prompt Specialist

GOAL: Read the drafted thread text and generate a single Nano Banana 2 image prompt that captures the core narrative as a powerful editorial visual.

RULES:
- Style: Subtle, editorial, photojournalistic. NOT a cartoon.
- NO text, labels, or speech bubbles in the image.
- NO real politician faces — use generic figures or symbolic representations.
- Focus on bold visual metaphors that convey the political failure.
- The prompt should result in a 16:9, 2K JPEG.

YOUR TASK:
1. Read the thread draft provided to you.
2. Identify the central narrative/metaphor.
3. Write a single, detailed image generation prompt (2-4 sentences).
4. Call the generate_nano_banana_image tool with your prompt.
5. Return the local file path of the generated image."""


ORCHESTRATOR_PROMPT = """You are the pipeline orchestrator for Cold Open, an Indian political accountability Twitter automation engine.

Execute this EXACT sequence — do NOT skip steps or change the order:

STEP 1: Call the scrape_critical_tweets tool to get raw tweets from independent journalists.

STEP 2: Spawn the "curator" agent. Pass it all the raw tweets. It will score them and return a CurationResult JSON with: headline, key_fact, primary_politician_involved, url.

STEP 3: Spawn BOTH of these agents IN PARALLEL (in the same turn):
  - "forensics" agent — pass it the CurationResult so it can search for media of the politician
  - "researcher" agent — pass it the CurationResult so it can run deep Perplexity research

STEP 4: Spawn the "framer-writer" agent. Pass it ALL context: the CurationResult, the forensics media path, and the full research briefing. It will develop the narrative angle and write the complete thread draft.

STEP 5: Spawn BOTH of these agents IN PARALLEL (in the same turn):
  - "thread-architect" agent — pass it the draft text to split into 1-3 long-form tweets
  - "image-generator" agent — pass it the draft text to generate an editorial image

STEP 6: Combine the results. Take the tweets array from thread-architect and the media_path from image-generator. Return the final ThreadResult JSON:
{"tweets": ["tweet1", "tweet2", ...], "media_path": "drafts/thread_image.jpg"}

CRITICAL RULES:
- Steps 3 and 5 MUST spawn agents in parallel (both in one turn).
- Always pass the full context — subagents cannot see previous agent outputs unless you include them.
- Return ONLY the final ThreadResult JSON. No commentary."""
