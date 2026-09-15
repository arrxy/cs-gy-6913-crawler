import requests

from page_extractor import extract_html_and_links
from search_engine import search_engine_query

def init_crawler(text: str) -> None:
    print(f"Searching for: {text}")
    search_links = search_engine_query(text)
    print("Results found:", len(search_links))
    crawler(search_links)

def crawler(search_links: list[str]) -> list[dict[str, str | list[str]]]:
    pages = []
    for url in search_links:
        try:
            html, links = extract_html_and_links(url)
        except (requests.RequestException, ValueError) as error:
            print(f"Skipped {url}: {error}")
            continue

        pages.append({"url": url, "html": html, "links": links})
        print(f"{url}: {len(html)} HTML characters, {len(links)} links")

    return pages