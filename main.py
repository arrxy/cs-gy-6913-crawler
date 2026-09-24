import uuid

from src.crawler import init_crawler
from src.custom_logger import CrawlLogger


def main() -> None:
    text = input("Enter your initial search query: ")
    file_path = f"logs/{input('Log file path (Enter for a unique file in logs/): ').strip() or uuid.uuid4().hex}.log"
    print(f"Logging crawl events to: {file_path}")
    print(f"Crawl time (in minutes): ")
    minutes = input().strip()
    if not minutes.isdigit():
        print("Invalid input. Using default crawl time of 10 minutes.")
        minutes = 10
    else:
        minutes = int(minutes)
    num_threads = 128
    print(f"Starting crawl for {minutes} minutes with {num_threads} threads...")
    with CrawlLogger(file_path=file_path) as logger:
        init_crawler(text, logger=logger, num_threads = num_threads, max_seconds = minutes * 60)

if __name__ == '__main__':
    main()
