from urllib.parse import urlencode, urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def search_engine_call(text: str) -> list[str]:
    search_url = (
        "https://html.duckduckgo.com/html/?"
        + urlencode({"q": text})
    )

    raw_links = extract_page_links(
        search_url,
        selector="a.result__a[href], a.result-link[href]",
    )

    links = []

    for url in raw_links:
        destination = parse_qs(urlparse(url).query).get("uddg")
        if destination:
            url = destination[0]

        parsed = urlparse(url)
        host = parsed.hostname or ""
        # Skip DuckDuckGo ad redirects.
        if (host == "duckduckgo.com" or host.endswith(".duckduckgo.com")) and parsed.path == "/y.js":
            continue

        if parsed.scheme in {"http", "https"}:
            links.append(url)

    return list(dict.fromkeys(links))

def extract_page_links(
    url: str,
    selector: str = "a[href]",
) -> list[str]:
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=".crawler-browser",
            headless=False,
        )

        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded")

            try:
                page.locator(selector).first.wait_for(timeout=10_000)
            except PlaywrightTimeoutError:
                input(
                    "Check the browser. Complete any CAPTCHA and wait "
                    "for the page to load, then press Enter here..."
                )
                page.locator(selector).first.wait_for(timeout=30_000)

            soup = BeautifulSoup(page.content(), "html.parser")
            links = []

            for link in soup.select(selector):
                destination = urljoin(page.url, link["href"])
                if urlparse(destination).scheme in {"http", "https"}:
                    links.append(destination)

            return list(dict.fromkeys(links))

        finally:
            context.close()

def extract_html(text: str):
    pass

def crawler(text: str):
    links = search_engine_call(text)
    print("Results found:", len(links))

    for url in links:
        print(url)

if __name__ == '__main__':
    text = input("Enter your search query: ")
    crawler(text)