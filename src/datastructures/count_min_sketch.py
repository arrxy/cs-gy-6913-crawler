import hashlib
import math
from threading import Lock

'''
A Count-Min Sketch estimates how many times an item has been seen, like a Hash Map of counts,
but in fixed memory no matter how many distinct items show up. The catch is that counts can
come out too high, never too low. That's fine for tracking rough frequencies during a crawl
(how often a URL or domain shows up) without keeping a counter for every single one.

Count-Min Sketch Workings:
1. Size
    ε = error_rate, how far an estimate can overshoot, as a fraction of the total count
    δ = error_probability, the chance an estimate overshoots by more than that
    width (w) = ceil(e / ε)
    no of hash functions / rows (d) = ceil(ln(1 / δ))

2. Hash Functions
    _positions() picks one column per row using SHA-256. Same trick as the Bloom Filter:
    prefix the item with the row index before hashing, so each row gets its own hash.

3. Updating and Querying Counts
    add() bumps the counter at (row, column) in every row by count.
    estimate() reads those same d counters and returns the smallest.
    Other items can land in the same cell, so every counter is at least the true count.
    Some rows collide more than others, and the minimum is the row with the fewest collisions.
    __contains__ is True when the estimate is above 0. False positives are possible, false negatives aren't.
'''

class CountMinSketch:
    def __init__(
            self,
            error_rate: float = 0.001,
            error_probability: float = 0.001
        ):
        # Rows correspond to the number of hash functions, and columns correspond to the width of the sketch.
        error_probability = max(0.000001, min(0.999999, error_probability))
        error_rate = max(0.000001, min(0.999999, error_rate))

        self.width = math.ceil(math.e / error_rate)
        self.num_hashes = math.ceil(math.log(1 / error_probability))

        self.table = [
            [0] * self.width
            for _ in range(self.num_hashes)
        ]
        self.total_count = 0
        self.lock = Lock()

    def _positions(self, item: str):
        data = item.encode("utf-8")
        for row in range(self.num_hashes):
            prefix = row.to_bytes(4, byteorder="big")
            digest = hashlib.sha256(prefix + data).digest()
            column = int.from_bytes(digest, byteorder="big") % self.width
            yield row, column

    def add(self, item: str, count: int = 1) -> None:
        count = max(count, 0)
        with self.lock:
            for row, column in self._positions(item):
                self.table[row][column] += count
            self.total_count += count

    def estimate(self, item: str) -> int:
        with self.lock:
            return min(
                self.table[row][column]
                for row, column in self._positions(item)
            )

    def __contains__(self, item: str) -> bool:
        return self.estimate(item) > 0