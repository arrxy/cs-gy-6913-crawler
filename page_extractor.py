from urllib.parse import urljoin, urlparse
import requests
from pathlib import Path
from uuid import uuid4
import hashlib

from bs4 import BeautifulSoup

output_dir = Path("downloads") / uuid4().hex
output_dir.mkdir(parents=True, exist_ok=False)

def hydrate_url(soup: BeautifulSoup, url: str) -> str:
    base_tag = soup.find("base", href=True)
    if base_tag:
        base_url = urljoin(url, base_tag["href"])
        return base_url
    return url

def download_html(html: str, url: str) -> Path:
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    filename = f"{urlparse(url).hostname}_{url_hash}.html"
    file_path = output_dir / filename
    file_path.write_text(html, encoding="utf-8")
    return file_path

def check_link_validity(link: str) -> bool:
    if not link:
        return False
    try:
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
    except ValueError:
        return False
    if "cgi" in link.lower():
        return False
    return True

def extract_html_and_links(
    url: str,
    selector: str = "a[href]",
    max_bytes: int = 5 * 1024 * 1024,
) -> tuple[str, list[str]]:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer.")
    if not check_link_validity(url):
        raise ValueError(f"Invalid URL: {url}.")

    with requests.get(url, timeout=30, stream=True) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"Expected HTML, received {content_type}.")

        body = bytearray()
        for chunk in response.iter_content(chunk_size=min(64 * 1024, max_bytes + 1)):
            if len(body) + len(chunk) > max_bytes:
                raise ValueError(f"HTML exceeds the {max_bytes:,}-byte download limit.")
            body.extend(chunk)

        try:
            html = body.decode(response.encoding or "utf-8", errors="replace")
        except LookupError:
            html = body.decode("utf-8", errors="replace")
    download_html(html, url)
    soup = BeautifulSoup(html, "html.parser")

    base_url = hydrate_url(soup, response.url)

    links = []
    for element in soup.select(selector):
        href = element.get("href")
        if not href:
            continue
        destination = urljoin(base_url, href.strip())
        if check_link_validity(destination):
            links.append(destination)

    return html, list(dict.fromkeys(links))