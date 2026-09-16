import hashlib
import math
from threading import Lock

class CountMinSketch:
    def __init__(
            self,
            error_rate: float = 0.001,
            error_probability: float = 0.001
        ):
        # Rows correspond to the number of hash functions, and columns correspond to the width of the sketch.
        if error_rate <= 0 or error_rate >= 1:
            raise ValueError("error_rate must be in the range (0, 1).")
        if error_probability <= 0 or error_probability >= 1:
            raise ValueError("error_probability must be in the range (0, 1).")
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