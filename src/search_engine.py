import os
from urllib.parse import urlparse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
def search_engine_query(text: str, max_results: int = 20) -> list[str]:
    max_results = min(max_results, 20)

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("Set the TAVILY_API_KEY environment variable before searching.")

    response = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "query": text,
            "search_depth": "basic",
            "max_results": max_results,
            "auto_parameters": False,
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=30,
    )
    response.raise_for_status()

    links = []
    for result in response.json().get("results", []):
        url = result.get("url")
        if url and urlparse(url).scheme in {"http", "https"}:
            links.append(url)

    return list(dict.fromkeys(links))[:max_results]
