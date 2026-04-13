"""Scrape kendonotes.wordpress.com kendo articles.

Usage:
    python scripts/scraping/scrape_kendonotes.py
    python scripts/scraping/scrape_kendonotes.py --dry-run
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

KENDONOTES_CONFIG = SiteConfig(
    site_name="kendonotes",
    source_folder="blogs/kendonotes",

    # WordPress.com listing page
    article_link_xpath=(
        '//h2[contains(@class, "entry-title")]/a | '
        '//h1[contains(@class, "entry-title")]/a | '
        '//h2/a[starts-with(@href, "https://kendonotes.wordpress.com/")]'
    ),
    pagination_next_xpath=(
        '//a[contains(@class, "next")] | '
        '//div[contains(@class, "nav-previous")]//a | '
        '//a[contains(text(), "Older posts")]'
    ),

    # Article page
    title_xpath='//h1[contains(@class, "entry-title")] | //h1[contains(@class, "post-title")]',
    date_xpath='//time/@datetime | //span[contains(@class, "posted-on")]//time/@datetime',
    content_xpath='//div[contains(@class, "entry-content")]',
    content_fallback_xpath='//div[contains(@class, "post-content")]',

    stop_texts=["Share this:", "Like this:", "Related", "Share this"],
    skip_prefixes=["Loading", "Click to share", "Click to email"],

    source_patterns=["source:", "originally published", "original article"],
    translator_patterns=["translated by", "translation by"],
    strip_patterns=["source:", "originally published", "translated by", "translation by"],
)


def main():
    parser = make_arg_parser("Scrape kendonotes.wordpress.com articles")
    args = parser.parse_args()
    run_scraper(KENDONOTES_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
