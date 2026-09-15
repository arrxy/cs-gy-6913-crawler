from urllib.parse import urljoin, urlparse
import requests

from bs4 import BeautifulSoup


def hydrate_url(soup: BeautifulSoup, url: str) -> str:
    base_tag = soup.find("base", href=True)
    if base_tag:
        base_url = urljoin(url, base_tag["href"])
        return base_url
    return url

def extract_html_and_links(
    url: str,
    selector: str = "a[href]",
) -> tuple[str, list[str]]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
        raise ValueError(f"Expected HTML, received {content_type}.")

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    base_url = hydrate_url(soup, response.url)

    links = []
    for element in soup.select(selector):
        href = element.get("href")
        if not href:
            continue
        destination = urljoin(base_url, href.strip())
        if urlparse(destination).scheme in {"http", "https"}:
            links.append(destination)

    return html, list(dict.fromkeys(links))