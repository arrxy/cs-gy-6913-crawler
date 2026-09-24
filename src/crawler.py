from collections import defaultdict
from queue import Empty, Queue
from threading import Thread
from time import monotonic
from urllib.parse import urldefrag, urlparse

import requests

from src.datastructures import BloomFilter, CrawlPriorityQueue
from src.custom_logger import CrawlLogger
from src.page_extractor import FetchMetadata, extract_html_and_links
from src.robots import robots_allowed, RobotsDisallowed
from src.search_engine import search_engine_query

'''
The crawler itself. It takes a search query, uses the results as seed URLs, and then crawls
outward with a pool of worker threads until it hits a page limit, a time limit, or runs out of
URLs. The main thread is the only one that touches the priority queue and the Bloom filter;
workers only fetch pages and hand results back.

Crawler Workings:
1. Seeding
    init_crawler() runs the search query and passes the result links to _crawler() as seeds
    at distance 0. Search failures are logged and re-raised.

2. Limits
    num_threads is clamped to 1-64 and max_pages to 1-100,000.
    max_seconds sets a deadline measured with monotonic(), which isn't affected by clock changes.

3. Discovering URLs
    enqueue() strips the #fragment, rejects anything that isn't absolute http/https, and checks
    the Bloom filter before pushing to the priority queue. A Bloom filter hit is counted as
    "possibly_already_discovered", since it could be a false positive that skips a new URL.

4. Threads and Queues
    Two plain Queues connect the main thread and the workers:
    tasks: main thread -> workers, holds (node, priority) to fetch
    results: workers -> main thread, holds (node, html, links, error)
    Workers loop on tasks.get() and exit when they receive None.
    Every task produces exactly one result, even on failure, so in_flight always stays accurate.

5. Worker
    Each worker logs the start of a visit, fetches the page, and logs the finish with size,
    status, timing, and outcome. Errors are caught and sent back as part of the result instead
    of killing the thread. If the error carries an HTTP response (e.g. a 404), its status and
    final URL are copied into the metadata first.

6. Main Loop
    While there are URLs queued or fetches in flight:
    - check the deadline and switch to stopping once it passes
    - hand out tasks until every thread is busy, the page limit would be reached
      (pages_collected + in_flight), or the queue is empty
    - wait up to 0.2s for a result, so the deadline keeps getting checked while threads are busy
    Once stopping is set, no new tasks go out, but in-flight fetches are allowed to finish.

7. Accepting Results
    accept_result() counts only successful fetches toward pages_collected and records the domain
    visit in the priority queue. Expected failures (requests errors, ValueError) are dropped quietly.
    Anything else is a bug and gets re-raised. Links from a page are only queued while not stopping.

8. Shutdown
    The finally block always runs, whether the crawl finished, hit a limit, errored, or got Ctrl+C.
    It sends one None per thread, waits for all workers to finish, drains any leftover results
    without discovering new links, and logs a crawl summary with stop reason, pages collected,
    throughput, pending URLs, and skip counts.
'''

def init_crawler(
    text: str,
    *,
    num_threads: int = 16,
    max_pages: int = 100_000,
    max_seconds: float = 1 * 60,
    logger: CrawlLogger
) -> None:
    logger.event("search_started", query=text)
    try:
        search_links = search_engine_query(text)
    except BaseException as error:
        logger.event("search_failed", level="ERROR", error_type=type(error).__name__, error=str(error))
        raise
    logger.event("search_completed", result_count=len(search_links), seed_urls=search_links)
    _crawler(search_links, num_threads=num_threads, max_pages=max_pages,
             max_seconds=max_seconds, logger=logger)


def _crawler(
    search_links: list[str],
    *,
    num_threads: int = 4,
    max_pages: int = 100_000,
    max_seconds: float = 3600,
    logger: CrawlLogger,
) -> None:
    num_threads = min(64, max(1, num_threads))
    max_pages = min(100_000, max(1, max_pages))

    start_time = monotonic()
    deadline = start_time + max_seconds
    discovered_urls = BloomFilter(expected_items=1_000_0000, false_positive_rate=0.001, logger = logger)
    pages_collected = 0
    priority_queue = CrawlPriorityQueue()
    skip_counts = defaultdict(int)
    logger.event("crawl_started", num_threads=num_threads, max_pages=max_pages,
                 max_seconds=max_seconds, seed_count=len(search_links),
                 priority_formula="1 / log2(domain_pages + 2)",
                 size_unit="decompressed response bytes", visit_order="request start")

    def enqueue(url: str, distance: int):
        try:
            url = urldefrag(url)[0]
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Expected an absolute HTTP or HTTPS URL")
            if url in discovered_urls:
                skip_counts["possibly_already_discovered"] += 1
                return
            priority_queue.push(url=url, distance=distance)
            discovered_urls.add(url)
        except ValueError as error:
            skip_counts["invalid_url"] += 1
            logger.event("url_skipped", level="WARNING", url=url, reason="invalid_url", error=str(error))

    for url in search_links:
        enqueue(url, 0)

    tasks = Queue()
    results = Queue()

    def worker():
        while True:
            task = tasks.get()
            if task is None:
                return
            node, priority = task
            metadata = FetchMetadata()
            visit = None
            html = links = failure = None
            started = monotonic()
            try:
                if not robots_allowed(node.url):
                    raise RobotsDisallowed(f"Blocked by robots.txt: {node.url}")
                visit = logger.begin_visit(
                    node.url, domain=urlparse(node.url).hostname,
                    priority_domain=node.domain,
                    domain_priority=priority, depth=node.distance,
                )
                html, links = extract_html_and_links(node.url, metadata=metadata)
            except RobotsDisallowed as error:
                failure = error
                metadata.final_url = node.url
                logger.event("robots_disallowed", level="INFO", url=node.url, domain=node.domain)
            except BaseException as error:
                failure = error
                response = getattr(error, "response", None)
                if response is not None:
                    metadata.status_code = response.status_code
                    metadata.final_url = response.url

            finally:
                if visit is not None:
                    try:
                        logger.finish_visit(
                            visit, size_bytes=metadata.size_bytes,
                            status_code=metadata.status_code, final_url=metadata.final_url,
                            outcome="success" if failure is None else "failed",
                            error=None if failure is None else f"{type(failure).__name__}: {failure}",
                            elapsed_seconds=monotonic() - started,
                            saved_path=metadata.saved_path, content_type=metadata.content_type,
                        )
                    except BaseException as logging_error:
                        if failure is None:
                            failure = logging_error
                results.put((node, html, links, failure))

    threads = []
    in_flight = 0
    stopping = False
    stop_reason = "frontier_exhausted"

    def accept_result(result, discover=True, raise_unexpected=True):
        nonlocal stopping, stop_reason, pages_collected
        node, html, links, error = result
        if error is not None:
            if not isinstance(error, (requests.RequestException, ValueError)):
                if raise_unexpected:
                    raise error
                logger.event("worker_error", level="ERROR", url=node.url,
                             error_type=type(error).__name__, error=str(error))
            return
        priority_queue.visit_domain(node.domain)
        pages_collected += 1
        if pages_collected >= max_pages and not stopping:
            stopping = True
            stop_reason = "page_limit"
            logger.event("crawl_stopping", reason=stop_reason, max_pages=max_pages)
        if discover and not stopping:
            for link in links:
                enqueue(link, node.distance + 1)

    try:
        for index in range(num_threads):
            thread = Thread(target=worker, name=f"crawler-{index + 1}")
            thread.start()
            threads.append(thread)

        while not priority_queue.empty() or in_flight:
            if not stopping and monotonic() >= deadline:
                stopping = True
                stop_reason = "time_limit"
                logger.event("crawl_stopping", reason=stop_reason, max_seconds=max_seconds)
            while (not stopping and in_flight < num_threads
                   and pages_collected + in_flight < max_pages and not priority_queue.empty()):
                if monotonic() >= deadline:
                    stopping = True
                    stop_reason = "time_limit"
                    logger.event("crawl_stopping", reason=stop_reason, max_seconds=max_seconds)
                    break
                node, priority = priority_queue.pop()
                tasks.put((node, priority))
                in_flight += 1
            if not in_flight:
                break
            try:
                result = results.get(timeout=0.2)
            except Empty:
                continue
            in_flight -= 1
            accept_result(result)
    except KeyboardInterrupt:
        stop_reason = "interrupted"
        stopping = True
        logger.event("crawl_stopping", level="WARNING", reason=stop_reason)
        raise
    except BaseException as error:
        stop_reason = "error"
        stopping = True
        logger.event("crawl_error", level="ERROR", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        for _ in threads:
            tasks.put(None)
        for thread in threads:
            thread.join()
        try:
            while True:
                try:
                    result = results.get_nowait()
                except Empty:
                    break
                try:
                    accept_result(result, discover=False, raise_unexpected=False)
                except Exception as error:
                    logger.event("shutdown_result_error", level="ERROR",
                                 error_type=type(error).__name__, error=str(error))
        finally:
            elapsed = monotonic() - start_time
            logger.event("crawl_summary", stop_reason=stop_reason, pages_collected=pages_collected,
                         elapsed_seconds=round(elapsed, 6),
                         pages_per_second=round(pages_collected / elapsed, 3) if elapsed else 0,
                         pending_urls=priority_queue.size(), num_threads=num_threads,
                         skipped=dict(skip_counts), **logger.stats)
