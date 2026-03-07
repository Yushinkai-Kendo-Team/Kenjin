"""Scrape kendo3ka.wordpress.com Vietnamese kendo blog articles.

Usage:
    python scripts/scraping/scrape_kendo3ka.py
    python scripts/scraping/scrape_kendo3ka.py --dry-run
    python scripts/scraping/scrape_kendo3ka.py --source blogs
"""

from base_scraper import SiteConfig, run_scraper, make_arg_parser

KENDO3KA_CONFIG = SiteConfig(
    site_name="kendo3ka",
    source_folder="blogs/kendo3ka",

    # Listing page
    article_link_xpath='//article//a[contains(@rel, "bookmark")]',
    pagination_next_xpath=(
        '//a[contains(@class, "next")] | '
        '//a[contains(text(), "c\u0169") and contains(text(), "h\u01a1n")]'
    ),

    # Article page
    title_xpath=(
        '//h1[contains(@class, "post-title")] | '
        '//h2[contains(@class, "post-title")]'
    ),
    date_xpath=(
        '//a[contains(@class, "post-date")] | '
        '//time[contains(@class, "post-date")] | '
        '//time/@datetime'
    ),
    content_xpath='//div[contains(@class, "post-content")]',
    content_fallback_xpath='//div[contains(@class, "entry-content")]',

    # Vietnamese content filtering
    stop_texts=["Chia s\u1ebb:", "C\u00f3 li\u00ean quan", "Like this:", "Related"],
    skip_prefixes=["Loading", "Click to share"],

    # Vietnamese attribution
    source_patterns=["ngu\u1ed3n:", "source:"],
    translator_patterns=["d\u1ecbch:", "ng\u01b0\u1eddi d\u1ecbch:", "nh\u00f3m d\u1ecbch:"],
    strip_patterns=[
        "ngu\u1ed3n:", "source:", "ng\u01b0\u1eddi d\u1ecbch:",
        "nh\u00f3m d\u1ecbch:", "d\u1ecbch:", "translate:",
    ],
)


def main():
    parser = make_arg_parser("Scrape kendo3ka.wordpress.com")
    args = parser.parse_args()
    run_scraper(KENDO3KA_CONFIG, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
