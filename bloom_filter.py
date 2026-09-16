import hashlib
import math
from threading import Lock
from typing import Iterator


class BloomFilter:
    def __init__(
        self,
        expected_items: int = 100_000,
        false_positive_rate: float = 0.001,
    ):
        if isinstance(expected_items, bool) or not isinstance(expected_items, int):
            raise ValueError("expected_items must be a positive integer")
        if expected_items <= 0:
            raise ValueError("expected_items must be a positive integer")
        if not 0 < false_positive_rate < 1:
            raise ValueError("false_positive_rate must be between 0 and 1")

        self.capacity = expected_items
        self.false_positive_rate = false_positive_rate
        self.num_bits = math.ceil(
            -expected_items * math.log(false_positive_rate) / math.log(2) ** 2
        )
        self.num_hashes = max(
            1, round(self.num_bits / expected_items * math.log(2))
        )
        self.bits = bytearray((self.num_bits + 7) // 8)
        self.lock = Lock()
        self._insertions = 0

    def _positions(self, item: str) -> Iterator[int]:
        data = item.encode("utf-8")
        for index in range(self.num_hashes):
            prefix = index.to_bytes(4, byteorder="big")
            digest = hashlib.sha256(prefix + data).digest()
            yield int.from_bytes(digest, byteorder="big") % self.num_bits

    def add(self, item: str) -> None:
        positions = tuple(self._positions(item))
        with self.lock:
            if all(self.bits[p // 8] & (1 << (p % 8)) for p in positions):
                return
            # Refuse new entries rather than silently saturating the filter.
            if self._insertions >= self.capacity:
                raise OverflowError(
                    "BloomFilter capacity reached; use a larger expected_items "
                    "value before starting the crawl"
                )
            for position in positions:
                self.bits[position // 8] |= 1 << (position % 8)
            self._insertions += 1

    def __contains__(self, item: str) -> bool:
        positions = tuple(self._positions(item))
        with self.lock:
            return all(
                self.bits[p // 8] & (1 << (p % 8))
                for p in positions
            )
