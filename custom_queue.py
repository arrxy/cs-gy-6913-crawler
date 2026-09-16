import heapq
from typing import Tuple
from urllib.parse import urlparse, urldefrag
from math import log2
from itertools import count


import tldextract

from count_min_sketch import CountMinSketch

extract_domain = tldextract.TLDExtract(suffix_list_urls=None)

class Node:
    def __init__(self, url: str, domain: str, distance: int):
        self.url = url
        self.domain = domain
        self.distance = distance

class CrawlPriorityQueue:
    def __init__(self):
        self.queue = []
        # Use CountMinSketch to track the number of times each domain has been visited
        self.domain_visited = CountMinSketch()
        self.sequence = count()

    def visit_domain(self, domain: str) -> None:
        self.domain_visited.add(domain)

    def _priority(self, domain: str) -> float:
        # Lower priority for domains that have been visited more frequently
        p = self.domain_visited.estimate(domain)
        # Log2 0 is undefined and Log2 1 is 0, add 2 to avoid division by zero and negative priority
        return 1.0 / (log2(p + 2))

    def push(self, url: str, distance: int = 0) -> None:
        url = urldefrag(url)[0]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Expected an absolute HTTP or HTTPS URL")
        domain = extract_domain(parsed.hostname).domain.lower()
        node = Node(url, domain, distance)
        heapq.heappush(self.queue, (-self._priority(domain), next(self.sequence), node))

    def size(self) -> int:
        return len(self.queue)

    def empty(self) -> bool:
        return len(self.queue) == 0

    def peek(self) -> Tuple[Node, float]:
        if not self.queue or len(self.queue) == 0:
            raise IndexError("peek from an empty priority queue")
        while self.queue:
            neg_priority, seq, node = self.queue[0]
            updated_node_neg_priority = -self._priority(node.domain)
            if updated_node_neg_priority != neg_priority:
                heapq.heappop(self.queue)
                heapq.heappush(self.queue, (updated_node_neg_priority, seq, node))
            else:
                return node, -neg_priority
        raise IndexError("Priority queue is empty")

    def pop(self) -> Tuple[Node, float]:
        if not self.queue or len(self.queue) == 0:
            raise IndexError("pop from an empty priority queue")
        while self.queue:
            neg_priority, seq, node = heapq.heappop(self.queue)
            updated_node_neg_priority = -self._priority(node.domain)
            if updated_node_neg_priority != neg_priority:
                heapq.heappush(self.queue, (updated_node_neg_priority, seq, node))
            else:
                return node, -neg_priority
        raise IndexError("Priority queue is empty")
