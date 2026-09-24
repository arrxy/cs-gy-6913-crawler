from urllib.parse import urljoin, urlparse
import requests
from pathlib import Path
from uuid import uuid4
import hashlib
from dataclasses import dataclass

from bs4 import BeautifulSoup

'''
Fetches a single page, saves its HTML to disk, and pulls out the links on it for the crawler
to queue up. Everything that could go wrong on the web (redirects, huge files, non-HTML content,
broken charsets, junk links) is handled here so the rest of the crawler only ever sees clean,
absolute http/https URLs.

Fetcher Workings:
1. Output Folder
    Each run saves pages into downloads/<random uuid>/, created once at import time.
    Files are named <hostname>_<sha256 of url>.html. The hash keeps names unique and
    filesystem-safe, since URLs are full of / ? & and friends. The hostname is just for readability.

2. FetchMetadata
    The caller passes one in and extract_html_and_links() fills it in as it goes.
    It's a parameter rather than a return value so that if the fetch fails partway (404, too big,
    wrong content type), the caller still gets whatever was recorded before the exception.

3. Link Validity
    check_link_validity() only lets through absolute http/https URLs with a hostname.
    mailto:, javascript:, malformed URLs, and anything containing "cgi" get dropped.

4. Downloading
    requests streams the body (stream=True) so we can stop early instead of pulling the whole thing.
    Status code and final URL are recorded before raise_for_status(), so failures still show up in metadata.
    Only text/html and application/xhtml+xml are accepted; a missing Content-Type is let through.
    The body is read in chunks of up to 64 KB and the download aborts past max_bytes (5 MB by default).
    Note that timeout=5 is per read, not for the whole download.

5. Link Extraction
    Relative links resolve against the final URL after redirects, unless the page has a
    <base href="..."> tag, in which case hydrate_url() makes that the base instead.
    Every href is joined into an absolute URL, validated, and deduplicated with dict.fromkeys(),
    which keeps the order links appeared on the page.
'''

output_dir = Path("downloads") / uuid4().hex
output_dir.mkdir(parents=True, exist_ok=False)


@dataclass
class FetchMetadata:
    status_code: int | None = None
    final_url: str | None = None
    size_bytes: int = 0
    content_type: str | None = None
    saved_path: str | None = None


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
    *,
    metadata: FetchMetadata | None = None,
) -> tuple[str, list[str]]:
    if not check_link_validity(url):
        raise ValueError(f"Invalid URL: {url}.")

    if metadata is None:
        metadata: FetchMetadata = FetchMetadata()
    with requests.get(url, timeout=5, stream=True) as response:
        metadata.status_code = response.status_code
        metadata.final_url = response.url
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        metadata.content_type = content_type or None
        if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"Expected HTML, received {content_type}.")

        body = bytearray()
        for chunk in response.iter_content(chunk_size=min(64 * 1024, max_bytes + 1)):
            metadata.size_bytes += len(chunk)
            if len(body) + len(chunk) > max_bytes:
                raise ValueError(f"HTML exceeds the {max_bytes:,}-byte download limit.")
            body.extend(chunk)

        try:
            html = body.decode(response.encoding or "utf-8", errors="replace")
        except LookupError:
            html = body.decode("utf-8", errors="replace")
    metadata.saved_path = str(download_html(html, url).resolve())
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