"""Scrape kenshi247.net English kendo theory articles.

Usage:
    python scripts/scraping/scrape_kenshi247.py
    python scripts/scraping/scrape_kenshi247.py --dry-run
    python scripts/scraping/scrape_kenshi247.py --source kenshi247
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

KENSHI247_CONFIG = SiteConfig(
    site_name="kenshi247",
    source_folder="blogs/kenshi247",

    # Listing page — Twenty Twenty theme uses h2 > a without rel="bookmark"
    article_link_xpath=(
        '//h2[contains(@class, "entry-title")]/a | '
        '//h2/a[starts-with(@href, "https://kenshi247.net/blog/")]'
    ),
    pagination_next_xpath=(
        '//a[contains(@class, "next")] | '
        '//a[contains(text(), "Older Posts")]'
    ),

    # Article page (Twenty Twenty theme)
    title_xpath='//h1[contains(@class, "entry-title")]',
    date_xpath=(
        '//span[contains(@class, "post-date")]//a | '
        '//time/@datetime'
    ),
    content_xpath='//div[contains(@class, "entry-content")]',
    content_fallback_xpath='//div[contains(@class, "post-content")]',

    # English content filtering
    stop_texts=["Share this:", "Like this:", "Related", "Related Posts"],
    skip_prefixes=["Loading", "Click to share", "Click to email"],

    # English attribution
    source_patterns=["source:", "originally published", "original article"],
    translator_patterns=["translated by", "translation by", "translation:"],
    strip_patterns=[
        "source:", "originally published",
        "translated by", "translation by", "translation:",
    ],
)


def main():
    parser = make_arg_parser("Scrape kenshi247.net theory articles")
    args = parser.parse_args()
    run_scraper(KENSHI247_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
