"""DEPRECATED: Use scripts/scraping/scrape_kendo3ka.py or scrape_kenshi247.py instead.

This script is kept for backward compatibility. It delegates to the new
scraping module which runs all configured blog sources.

Usage (same as before):
    python scripts/scrape_blog.py
    python scripts/scrape_blog.py --dry-run
    python scripts/scrape_blog.py --source blogs
"""

import sys
import warnings
from pathlib import Path

# Add scripts/scraping/ to path so we can import the new modules
_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir / "scraping"))

warnings.warn(
    "scrape_blog.py is deprecated. "
    "Use scripts/scraping/scrape_kendo3ka.py or scrape_kenshi247.py instead.",
    DeprecationWarning,
    stacklevel=1,
)

from base_scraper import run_scraper_all, make_arg_parser  # noqa: E402


def main():
    parser = make_arg_parser("Scrape blog articles for YSK Kenjin (deprecated)")
    args = parser.parse_args()
    run_scraper_all(source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
