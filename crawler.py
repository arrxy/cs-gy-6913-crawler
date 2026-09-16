import requests

from count_min_sketch import CountMinSketch
from custom_queue import CrawlPriorityQueue
from page_extractor import extract_html_and_links
from search_engine import search_engine_query

def init_crawler(text: str) -> None:
    print(f"Searching for: {text}")
    search_links = search_engine_query(text)
    print("Results found:", len(search_links))
    _crawler(search_links)

def _crawler(search_links: list[str]) -> list[dict[str, str | list[str]]]:
    urls_visited = CountMinSketch()
    pages = []
    priority_queue = CrawlPriorityQueue()
    for url in search_links:
        priority_queue.push(url = url, distance = 0)

    while not priority_queue.empty():
        node, priority = priority_queue.pop()
        if urls_visited.__contains__(node.url):
            print(f"Skipped {node.url}: already visited")
            continue
        urls_visited.add(node.url)
        try:
            html, links = extract_html_and_links(node.url)
            priority_queue.visit_domain(node.domain)
            for link in links:
                if not urls_visited.__contains__(link):
                    priority_queue.push(url = link, distance = node.distance + 1)
        except (requests.RequestException, ValueError) as error:
            print(f"Skipped {node.url}: {error}")
            continue
        pages.append({"url": node.url, "html": html, "links": links})
        print(f"{node.url}: {len(html)} HTML characters, {len(links)} links")

    return pages