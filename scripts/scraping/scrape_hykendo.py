"""Scrape hy-kendo.com (Helsinki University Kendo) articles.

Usage:
    python scripts/scraping/scrape_hykendo.py
    python scripts/scraping/scrape_hykendo.py --dry-run
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

HYKENDO_CONFIG = SiteConfig(
    site_name="hykendo",
    source_folder="blogs/hykendo",

    article_link_xpath=(
        '//h2[contains(@class, "entry-title")]/a | '
        '//h2/a[starts-with(@href, "https://hy-kendo.com/")]'
    ),
    pagination_next_xpath=(
        '//a[contains(@class, "next")] | '
        '//a[contains(text(), "Older")] | '
        '//div[contains(@class, "nav-links")]//a[contains(@class, "next")]'
    ),

    title_xpath='//h1[contains(@class, "entry-title")] | //h1[contains(@class, "wp-block-post-title")]',
    date_xpath='//time/@datetime',
    content_xpath='//div[contains(@class, "entry-content")] | //div[contains(@class, "wp-block-post-content")]',
    content_fallback_xpath='//div[contains(@class, "post-content")]',

    stop_texts=["Share this:", "Like this:", "Related"],
    skip_prefixes=["Loading", "Click to share"],

    source_patterns=[],
    translator_patterns=[],
    strip_patterns=[],
)


def main():
    parser = make_arg_parser("Scrape hy-kendo.com articles")
    args = parser.parse_args()
    run_scraper(HYKENDO_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
