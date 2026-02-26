from crewai.tools import tool
from duckduckgo_search import DDGS
import requests
from pathlib import Path
import os
import json

@tool("Search And Download Forensics")
def search_and_download_forensics(query: str) -> str:
    """Useful to search for an official document, graph, or high-res politician portrait based on the query, and download it to the drafts/ folder. Input should be a specific search query like 'Narendra Modi official portrait' or 'Bridge collapse official report'. Returns the local file path or an error string."""
    try:
        results = DDGS().images(
            keywords=query,
            max_results=1,
            safesearch="off"
        )
        if not results:
            return "No images found."
            
        img_url = results[0].get("image")
        if not img_url:
            return "No image URL found in results."

        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(img_url, headers=headers, timeout=15)
        r.raise_for_status()
        
        output_dir = Path("drafts")
        output_dir.mkdir(exist_ok=True)
        img_path = output_dir / "agent4_forensic_media.jpg"
        img_path.write_bytes(r.content)
        
        return str(img_path)
    except Exception as e:
        return f"Error downloading media: {str(e)}"

@tool("Verify Fact via Web Search")
def verify_fact_via_web(headline: str) -> str:
    """Useful to verify a headline by searching the live web. Returns the DDG search result text."""
    try:
        results = DDGS().text(f"{headline} news", max_results=2)
        verification_context = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        return verification_context
    except Exception as e:
        return f"Verification Error: {str(e)}"
