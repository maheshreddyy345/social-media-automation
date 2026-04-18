"""Claude Agent SDK tool wrappers for existing Cold Open tools.

Wraps the existing synchronous tool functions as async SDK @tool definitions
and bundles them into a single MCP server for the pipeline orchestrator.
"""
import json
import asyncio
from typing import Any
from claude_agent_sdk import tool, create_sdk_mcp_server, ToolAnnotations

# Import the raw functions from existing tools
from tools.scraper_tool import scrape_critical_tweets as _scrape_tweets
from tools.scraper_tool import scrape_cartoonist_feed as _scrape_cartoonists
from tools.forensics_tool import search_and_download_forensics as _search_forensics
from tools.forensics_tool import verify_fact_via_web as _verify_fact
from tools.research_tool import perplexity_deep_research as _perplexity_research
from tools.image_tool import generate_nano_banana_image as _generate_image


@tool(
    "scrape_critical_tweets",
    "Scrape the latest political tweets from 17 targeted independent Indian journalists on X/Twitter. Returns a JSON string of up to 30 tweets with media.",
    {},
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def scrape_critical_tweets(args: dict[str, Any]) -> dict[str, Any]:
    result = await asyncio.to_thread(_scrape_tweets.invoke, "")
    return {"content": [{"type": "text", "text": result}]}


@tool(
    "scrape_cartoonist_feed",
    "Scrape latest posts from top Indian political cartoonists sorted by engagement. Returns up to 50 tweets.",
    {},
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def scrape_cartoonist_feed(args: dict[str, Any]) -> dict[str, Any]:
    result = await asyncio.to_thread(_scrape_cartoonists.invoke, "")
    return {"content": [{"type": "text", "text": result}]}


@tool(
    "search_and_download_forensics",
    "Search DuckDuckGo for an official document, graph, or high-res politician portrait and download it. Input: a search query string. Returns local file path.",
    {"query": str},
)
async def search_and_download_forensics(args: dict[str, Any]) -> dict[str, Any]:
    result = await asyncio.to_thread(_search_forensics.invoke, args["query"])
    return {"content": [{"type": "text", "text": result}]}


@tool(
    "verify_fact_via_web",
    "Verify a headline by searching the live web via DuckDuckGo. Returns search result context.",
    {"headline": str},
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def verify_fact_via_web(args: dict[str, Any]) -> dict[str, Any]:
    result = await asyncio.to_thread(_verify_fact.invoke, args["headline"])
    return {"content": [{"type": "text", "text": result}]}


@tool(
    "perplexity_deep_research",
    "Run deep historical and political background research via Perplexity sonar-reasoning-pro API. Input: a research query. Returns a detailed briefing.",
    {"query": str},
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def perplexity_deep_research(args: dict[str, Any]) -> dict[str, Any]:
    result = await asyncio.to_thread(_perplexity_research.invoke, args["query"])
    return {"content": [{"type": "text", "text": result}]}


@tool(
    "generate_nano_banana_image",
    "Generate an editorial image using Fal AI Nano Banana 2. Input: a detailed image prompt. Returns the local file path of the downloaded JPEG (16:9, 2K).",
    {"image_prompt": str},
)
async def generate_nano_banana_image(args: dict[str, Any]) -> dict[str, Any]:
    result = await asyncio.to_thread(_generate_image, args["image_prompt"])
    return {"content": [{"type": "text", "text": result}]}


# Bundle all tools into one MCP server
tools_server = create_sdk_mcp_server(
    name="cold-open-tools",
    version="1.0.0",
    tools=[
        scrape_critical_tweets,
        scrape_cartoonist_feed,
        search_and_download_forensics,
        verify_fact_via_web,
        perplexity_deep_research,
        generate_nano_banana_image,
    ],
)
