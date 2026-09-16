from urllib.parse import urljoin, urlparse
import requests
from pathlib import Path
from uuid import uuid4

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
    filename = f"{urlparse(url).hostname}.html"
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
) -> tuple[str, list[str]]:
    if not check_link_validity(url):
        raise ValueError(f"Invalid URL: {url}.")
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
        raise ValueError(f"Expected HTML, received {content_type}.")

    html = response.text
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