"""Scrape weblog.tozando.com kendo articles.

Usage:
    python scripts/scraping/scrape_tozando.py
    python scripts/scraping/scrape_tozando.py --dry-run
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

TOZANDO_CONFIG = SiteConfig(
    site_name="tozando",
    source_folder="blogs/tozando",

    # WordPress listing page
    article_link_xpath=(
        '//h2[contains(@class, "entry-title")]/a | '
        '//h2/a[starts-with(@href, "https://weblog.tozando.com/")]'
    ),
    pagination_next_xpath=(
        '//a[contains(@class, "next")] | '
        '//a[contains(text(), "Older")] | '
        '//div[contains(@class, "nav-links")]//a[contains(@class, "next")]'
    ),

    title_xpath='//h1[contains(@class, "entry-title")] | //h1[contains(@class, "post-title")]',
    date_xpath='//time/@datetime | //span[contains(@class, "date")]',
    content_xpath='//div[contains(@class, "entry-content")]',
    content_fallback_xpath='//div[contains(@class, "post-content")]',

    stop_texts=["Share this:", "Like this:", "Related", "Related Posts"],
    skip_prefixes=["Loading", "Click to share"],

    source_patterns=[],
    translator_patterns=[],
    strip_patterns=[],
)


def main():
    parser = make_arg_parser("Scrape weblog.tozando.com kendo articles")
    args = parser.parse_args()
    run_scraper(TOZANDO_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
