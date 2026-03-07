"""Scrape kendoinfo.wordpress.com kendo articles by Geoff Salmon (7dan Kyoshi).

Usage:
    python scripts/scraping/scrape_kendoinfo.py
    python scripts/scraping/scrape_kendoinfo.py --dry-run
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

KENDOINFO_CONFIG = SiteConfig(
    site_name="kendoinfo",
    source_folder="blogs/kendoinfo",

    # Listing page — WordPress.com default theme, h2 > a links
    article_link_xpath=(
        '//h2/a[contains(@href, "kendoinfo.wordpress.com")]'
    ),
    pagination_next_xpath=(
        '//a[contains(text(), "Older Posts")]'
    ),

    # Article page (WordPress.com Starter theme — uses div.entry, not entry-content)
    title_xpath=(
        '//div[contains(@class, "posttitle")]//h2 | '
        '//h1[contains(@class, "entry-title")]'
    ),
    date_xpath=(
        '//time/@datetime | '
        '//span[contains(@class, "posted-on")]//a | '
        '//abbr[contains(@class, "published")]/@title'
    ),
    content_xpath='//div[@class="entry"]',
    content_fallback_xpath='//div[contains(@class, "entry-content")]',

    # English content filtering
    stop_texts=["Share this:", "Like this:", "Related", "Share this"],
    skip_prefixes=["Loading", "Click to share", "Click to email"],

    # Attribution (minimal for personal blog)
    source_patterns=[],
    translator_patterns=[],
    strip_patterns=[],
)


def main():
    parser = make_arg_parser("Scrape kendoinfo.wordpress.com")
    args = parser.parse_args()
    run_scraper(KENDOINFO_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
