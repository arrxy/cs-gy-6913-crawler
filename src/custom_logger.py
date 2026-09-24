import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class CrawlLogger:
    def __init__(self, file_path: str | Path | None = None):
        self.run_id = uuid4().hex
        self.file_path = Path(file_path or f"logs/crawl_{self.run_id}.jsonl").expanduser()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.file_path.open("a", encoding="utf-8")
        self.lock = Lock()
        self._stats = dict(attempted=0, completed=0, successful=0, failed=0, bytes_received=0)

    def _write(self, event: str, level: str = "INFO", **fields) -> None:
        record = {**fields, "event": event, "timestamp": _utc_now(),
                  "run_id": self.run_id, "level": level}
        self.file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self.file.flush()

    def event(self, event: str, level: str = "INFO", **fields) -> None:
        with self.lock:
            self._write(event, level, **fields)

    def begin_visit(self, url: str, **fields) -> dict:
        with self.lock:
            self._stats["attempted"] += 1
            visit = {"url": url, **fields, "visit_order": self._stats["attempted"],
                     "access_time": _utc_now()}
            self._write("visit_start", **visit)
            return visit

    def finish_visit(self, visit: dict, **fields) -> None:
        with self.lock:
            success = fields["outcome"] == "success"
            self._stats["completed"] += 1
            self._stats["successful" if success else "failed"] += 1
            self._stats["bytes_received"] += fields.get("size_bytes") or 0
            self._write("visit", "INFO" if success else "WARNING",
                        **visit, **fields, completion_time=_utc_now())

    @property
    def stats(self) -> dict:
        with self.lock:
            return self._stats.copy()

    def close(self) -> None:
        with self.lock:
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
