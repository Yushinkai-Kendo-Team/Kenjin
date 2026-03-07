"""Scrape shugo-nanseikan.blogspot.com kendo theory articles.

Usage:
    python scripts/scraping/scrape_nanseikan.py
    python scripts/scraping/scrape_nanseikan.py --dry-run
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

NANSEIKAN_CONFIG = SiteConfig(
    site_name="nanseikan",
    source_folder="blogs/nanseikan",

    # Listing page — Blogspot uses h3.post-title > a
    article_link_xpath=(
        '//h3[contains(@class, "post-title")]/a'
    ),
    pagination_next_xpath=(
        '//a[contains(@class, "blog-pager-older-link")] | '
        '//a[contains(text(), "Older Posts")]'
    ),

    # Article page (Blogspot standard)
    title_xpath=(
        '//h1[contains(@class, "post-title")] | '
        '//h3[contains(@class, "post-title")]'
    ),
    date_xpath=(
        '//abbr[contains(@class, "published")]/@title | '
        '//span[contains(@class, "timestamp")]//a | '
        '//h2[contains(@class, "date-header")]'
    ),
    content_xpath='//div[contains(@class, "post-body")]',
    content_fallback_xpath='//div[contains(@class, "entry-content")]',

    # English content filtering
    stop_texts=["Share to", "Posted by", "Labels:"],
    skip_prefixes=["Loading", "Click to share"],

    # Attribution
    source_patterns=[],
    translator_patterns=[],
    strip_patterns=[],
)


def main():
    parser = make_arg_parser("Scrape shugo-nanseikan.blogspot.com")
    args = parser.parse_args()
    run_scraper(NANSEIKAN_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
