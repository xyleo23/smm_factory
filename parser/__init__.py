"""Parser modules for content extraction."""

from parser.article_parser import ArticleParser, fetch_links_from_page
from parser.serp_parser import SerpParser

__all__ = ["ArticleParser", "SerpParser", "fetch_links_from_page"]
