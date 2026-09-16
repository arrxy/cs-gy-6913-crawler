from time import time

import requests

from bloom_filter import BloomFilter
from custom_queue import CrawlPriorityQueue
from page_extractor import extract_html_and_links
from search_engine import search_engine_query

def init_crawler(text: str) -> None:
    print(f"Searching for: {text}")
    search_links = search_engine_query(text)
    print("Results found:", len(search_links))
    _crawler(search_links)

def _crawler(search_links: list[str]) -> list[dict[str, str | list[str]]]:
    start_time = time()
    urls_visited = BloomFilter(expected_items=10_00_000, false_positive_rate=0.001)
    pages = []
    priority_queue = CrawlPriorityQueue()
    for url in search_links:
        priority_queue.push(url = url, distance = 0)

    while not priority_queue.empty():
        node, priority = priority_queue.pop()
        if node.url in urls_visited:
            print(f"Skipped {node.url}: possibly already visited")
            continue
        urls_visited.add(node.url)
        try:
            html, links = extract_html_and_links(node.url)
            priority_queue.visit_domain(node.domain)
            for link in links:
                if link not in urls_visited:
                    priority_queue.push(url = link, distance = node.distance + 1)
        except (requests.RequestException, ValueError) as error:
            print(f"Skipped {node.url}: {error}")
            continue
        pages.append({"url": node.url, "html": html, "links": links})
        print(f"{node.url}: {len(html)} HTML characters, {len(links)} links")
        if len(pages) >= 10_0000:
            print("Reached 10_0000 pages, stopping crawl.")
            break
        elapsed_time = time() - start_time
        if elapsed_time > 3600:
            print(f"Crawling completed in {elapsed_time / 3600:.2f} hours.")
            break


    return pages