"""Scrape kendojidai.com free kendo articles (translated from Japanese).

Usage:
    python scripts/scraping/scrape_kendojidai.py
    python scripts/scraping/scrape_kendojidai.py --dry-run
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

KENDOJIDAI_CONFIG = SiteConfig(
    site_name="kendojidai",
    source_folder="blogs/kendojidai",

    # WordPress listing page
    article_link_xpath=(
        '//h2[contains(@class, "entry-title")]/a | '
        '//h3[contains(@class, "entry-title")]/a | '
        '//h2/a[starts-with(@href, "https://kendojidai.com/")]'
    ),
    pagination_next_xpath=(
        '//a[contains(@class, "next")] | '
        '//a[contains(text(), "Next")] | '
        '//div[contains(@class, "nav-links")]//a[contains(@class, "next")]'
    ),

    # Article page
    title_xpath='//h1[contains(@class, "entry-title")] | //h1[contains(@class, "post-title")]',
    date_xpath='//time/@datetime | //span[contains(@class, "date")]',
    content_xpath='//div[contains(@class, "entry-content")]',
    content_fallback_xpath='//div[contains(@class, "post-content")] | //article//div[contains(@class, "content")]',

    stop_texts=["Share this:", "Like this:", "Related", "Related Posts", "Comments"],
    skip_prefixes=["Loading", "Click to share"],

    source_patterns=["source:", "kendo jidai", "originally published"],
    translator_patterns=["translated by", "translation by"],
    strip_patterns=["source:", "translated by", "translation by"],
)


def main():
    parser = make_arg_parser("Scrape kendojidai.com free articles")
    args = parser.parse_args()
    run_scraper(KENDOJIDAI_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
