"""Scrape kendoandphilosophy.wordpress.com kendo history/philosophy articles.

Usage:
    python scripts/scraping/scrape_kendophilosophy.py
    python scripts/scraping/scrape_kendophilosophy.py --dry-run
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

KENDOPHILOSOPHY_CONFIG = SiteConfig(
    site_name="kendophilosophy",
    source_folder="blogs/kendophilosophy",

    # Listing page — WordPress.com, h3 > a links (or h2)
    article_link_xpath=(
        '//h3/a[contains(@href, "kendoandphilosophy.wordpress.com")] | '
        '//h2/a[contains(@href, "kendoandphilosophy.wordpress.com")] | '
        '//h1[contains(@class, "entry-title")]/a'
    ),
    pagination_next_xpath=(
        '//a[contains(text(), "Older Posts")] | '
        '//a[contains(@class, "next")]'
    ),

    # Article page
    title_xpath=(
        '//h1[contains(@class, "entry-title")] | '
        '//h2[contains(@class, "post-title")] | '
        '//h3/a'
    ),
    date_xpath=(
        '//time/@datetime | '
        '//span[contains(@class, "posted-on")]//a'
    ),
    content_xpath='//div[contains(@class, "entry-content")]',
    content_fallback_xpath='//div[contains(@class, "post-content")]',

    # English content filtering
    stop_texts=["Share this:", "Like this:", "Related"],
    skip_prefixes=["Loading", "Click to share"],

    # Attribution
    source_patterns=[],
    translator_patterns=[],
    strip_patterns=[],
)


def main():
    parser = make_arg_parser("Scrape kendoandphilosophy.wordpress.com")
    args = parser.parse_args()
    run_scraper(KENDOPHILOSOPHY_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
