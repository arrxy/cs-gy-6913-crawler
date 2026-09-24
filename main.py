import uuid

from src.crawler import init_crawler
from src.custom_logger import CrawlLogger


def main() -> None:
    text = input("Enter your initial search query: ")
    file_path = f"logs/{input('Log file path (Enter for a unique file in logs/): ').strip() or uuid.uuid4().hex}.log"
    print(f"Logging crawl events to: {file_path}")
    minutes = 10
    num_threads = 64
    print(f"Starting crawl for {minutes} minutes with {num_threads} threads...")
    with CrawlLogger(file_path=file_path) as logger:
        init_crawler(text, logger=logger, num_threads = num_threads, max_seconds = minutes * 60)

if __name__ == '__main__':
    main()
