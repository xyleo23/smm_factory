"""Article parser for extracting content from web pages."""

from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger


class ArticleParser:
    """Parser for extracting article content from web pages."""
    
    TIMEOUT = 30.0
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    @classmethod
    async def fetch_html(cls, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL.
        Tries httpx first; on None or 403/429/503 falls back to Playwright.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None if failed
        """
        html = await cls._fetch_httpx(url)
        if html:
            return html
        return await cls._fetch_playwright(url)

    @classmethod
    async def _fetch_httpx(cls, url: str) -> Optional[str]:
        """Fetch HTML via httpx. Returns None on failure or 403/429/503."""
        try:
            async with httpx.AsyncClient(
                timeout=cls.TIMEOUT,
                headers={"User-Agent": cls.USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                if response.status_code in (403, 429, 503):
                    logger.warning(f"Blocked status {response.status_code} for {url}, will try Playwright")
                    return None
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {url}: {e.response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    @classmethod
    async def _fetch_playwright(cls, url: str) -> Optional[str]:
        """Fetch HTML via Playwright (fallback for blocked sites like vc.ru)."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=cls.USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                html = await page.content()
                await browser.close()
                return html
        except Exception as e:
            logger.error(f"Playwright error fetching {url}: {e}")
            return None
    
    @classmethod
    def parse_article(cls, html: str, base_url: str = "") -> Optional[Dict[str, Any]]:
        """
        Parse article content from HTML.
        
        Args:
            html: HTML content
            base_url: Base URL for resolving relative links
            
        Returns:
            Dictionary with title, content, and metadata or None if parsing failed
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove unwanted elements
            for tag in soup(["script", "style", "nav", "footer", "aside", "iframe"]):
                tag.decompose()
            
            # Try to find article title
            title = cls._extract_title(soup)
            
            # Try to find article content
            content = cls._extract_content(soup)
            
            if not title and not content:
                logger.warning("Could not extract title or content from HTML")
                return None
            
            return {
                "title": title,
                "content": content,
                "word_count": len(content.split()) if content else 0,
            }
            
        except Exception as e:
            logger.error(f"Error parsing article HTML: {e}")
            return None
    
    @classmethod
    def _extract_title(cls, soup: BeautifulSoup) -> Optional[str]:
        """Extract article title from HTML."""
        selectors = [
            "h1",
            "article h1",
            ".article-title",
            ".post-title",
            '[itemprop="headline"]',
            "meta[property='og:title']",
        ]
        
        for selector in selectors:
            if selector.startswith("meta"):
                tag = soup.select_one(selector)
                if tag and tag.get("content"):
                    return tag.get("content").strip()
            else:
                tag = soup.select_one(selector)
                if tag:
                    return tag.get_text(strip=True)
        
        # Fallback to <title> tag
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        
        return None
    
    @classmethod
    def _extract_content(cls, soup: BeautifulSoup) -> Optional[str]:
        """Extract article content from HTML."""
        selectors = [
            "article",
            ".article-content",
            ".post-content",
            ".entry-content",
            '[itemprop="articleBody"]',
            "main",
        ]
        
        for selector in selectors:
            tag = soup.select_one(selector)
            if tag:
                # Get all paragraphs
                paragraphs = tag.find_all("p")
                if paragraphs:
                    content = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    if len(content) > 100:
                        return content
        
        # Fallback: get all paragraphs from body
        paragraphs = soup.find_all("p")
        if paragraphs:
            content = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            if len(content) > 100:
                return content
        
        return None


async def fetch_links_from_page(url: str) -> List[str]:
    """
    Fetch all article links from a page.
    
    Args:
        url: URL of the page to parse
        
    Returns:
        List of article URLs found on the page
    """
    try:
        html = await ArticleParser.fetch_html(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        links = []
        
        # Find all links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            
            # Convert relative URLs to absolute
            if not href.startswith("http"):
                href = urljoin(url, href)
            
            # Filter out non-article links
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                # Skip navigation, social, and other non-content links
                if any(skip in href.lower() for skip in ["#", "javascript:", "mailto:", "tel:"]):
                    continue
                
                links.append(href)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        logger.info(f"Found {len(unique_links)} links on {url}")
        return unique_links
        
    except Exception as e:
        logger.error(f"Error fetching links from {url}: {e}")
        return []
