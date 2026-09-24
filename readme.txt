Folder Structure:
.
├── __pycache__
├── how_to_run.txt
├── logs
│   ├── <uuid>.log
├── main.py - (entry point of the program)
├── pyproject.toml - (contains project metadata and dependencies)
├── src - (source code directory)
│   ├── __init__.py - (marks the directory as a Python package)
│   ├── crawler.py - (contains the main crawling logic)
│   ├── custom_logger.py - (custom logging utility)
│   ├── datastructures - (contains custom data structures)
│   │   ├── __init__.py - (marks the directory as a Python package)
│   │   ├── bloom_filter.py - (implementation of a Bloom filter)
│   │   ├── count_min_sketch.py - (implementation of a Count-Min Sketch)
│   │   └── custom_queue.py - (implementation of a custom queue)
│   ├── page_extractor.py - (extracts relevant information from web pages)
│   ├── robots.py - (handles robots.txt parsing and compliance)
│   └── search_engine.py - (implements the search engine logic)
└── uv.lock

to run,
1. uv sync
2. uv run main.py

For more details, refer to the how_to_run.txt file.