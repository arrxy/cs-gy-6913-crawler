from functools import lru_cache
from urllib.parse import urlparse

import requests
from protego import Protego

USER_AGENT = "WSECrawler/1.0"

ALLOW_ALL = Protego.parse("")
DISALLOW_ALL = Protego.parse("User-agent: *\nDisallow: /")


class RobotsDisallowed(ValueError):
    pass

@lru_cache(maxsize=10_000)
def _fetch_robots(origin: str, timeout: float, max_bytes: int) -> Protego:
    try:
        with requests.get(
            f"{origin}/robots.txt",
            timeout=timeout,
            stream=True,
            headers={"User-Agent": USER_AGENT},
        ) as response:
            status = response.status_code
            if status in (401, 403):
                return DISALLOW_ALL
            if 400 <= status < 500:
                return ALLOW_ALL
            if status >= 300:
                return DISALLOW_ALL

            body = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                body.extend(chunk)
                if len(body) >= max_bytes:
                    break
    except requests.RequestException:
        return DISALLOW_ALL

    text = bytes(body[:max_bytes]).decode("utf-8", errors="replace")
    return Protego.parse(text)


def robots_allowed(url: str, timeout: float = 5, max_bytes: int = 500 * 1024) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return _fetch_robots(origin, timeout, max_bytes).can_fetch(url, USER_AGENT)