from crewai.tools import tool
import requests
import os

@tool("Perplexity Deep Research")
def perplexity_deep_research(query: str) -> str:
    """
    Synthesize deep historical and political background for a given news story using Perplexity's sonar-reasoning-pro API.
    Use this tool to automatically execute web searches to find facts, related past incidents, and politician statements.
    """
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return "Error: PERPLEXITY_API_KEY environment variable not set."
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "sonar-reasoning-pro",
        "messages": [
            {
                "role": "system",
                "content": "You are an investigative political researcher. Provide a detailed, brutally factual, and deeply researched report based on the query. Include specific names, dates, amounts, and historical comparisons if available."
            },
            {
                "role": "user",
                "content": query
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error connecting to Perplexity API: {e}"
