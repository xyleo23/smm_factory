"""Parser modules for content extraction."""

from parser.article_parser import (
    ArticleParser,
    fetch_dtf_articles,
    fetch_klerk_articles,
    fetch_links_from_page,
    fetch_rbc_companies_articles,
    fetch_rss_articles,
    fetch_timeweb_articles,
)
from parser.serp_parser import SerpParser

__all__ = [
    "ArticleParser",
    "SerpParser",
    "fetch_dtf_articles",
    "fetch_klerk_articles",
    "fetch_links_from_page",
    "fetch_rbc_companies_articles",
    "fetch_rss_articles",
    "fetch_timeweb_articles",
]
