"""Article parser for extracting content from web pages."""

import asyncio
import random
import xml.etree.ElementTree as ET
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


async def fetch_rss_articles(url: str) -> list[dict]:
    """
    Fetch articles directly from RSS feed.
    Returns list of dicts: {url, title, content, pub_date}
    """
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": ArticleParser.USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text
    except Exception as e:
        logger.error(f"RSS fetch error {url}: {e}")
        return []

    try:
        root = ET.fromstring(content)
        articles = []
        for item in root.iter("item"):
            full_text = None
            for child in item:
                if child.tag.split("}")[-1] == "full-text":
                    full_text = child.text
                    break

            link = item.findtext("link") or ""
            title = item.findtext("title") or ""
            description = item.findtext("description") or ""
            pub_date = item.findtext("pubDate") or ""

            content_text = full_text or description
            if link and content_text:
                articles.append({
                    "url": link.strip(),
                    "title": title.strip(),
                    "content": content_text.strip(),
                    "pub_date": pub_date.strip(),
                })
        logger.info(f"RSS parsed {len(articles)} articles from {url}")
        return articles
    except Exception as e:
        logger.error(f"RSS parse error {url}: {e}")
        return []


async def fetch_rbc_companies_articles(profile_url: str) -> list[dict]:
    """
    Парсит страницу автора (persons/...) на RBC Companies.
    Собирает статьи ТОЛЬКО со страницы автора (source.url), не из общей ленты.
    Возвращает список {url, title, content}
    """
    base = "https://companies.rbc.ru"
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": ArticleParser.USER_AGENT},
        follow_redirects=True,
    ) as client:
        # 1. GET страницы автора (один запрос)
        resp = await client.get(profile_url)
        resp.raise_for_status()
        html = resp.text

        # 2. Найти все <a href="/news/..."> или href="https://companies.rbc.ru/news/..." на странице
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            # Нормализуем: относительные /news/... или абсолютные https://companies.rbc.ru/news/...
            if href.startswith(base + "/news/"):
                path = href[len(base) :]
            elif href.startswith("/news/"):
                path = href
            else:
                continue
            # 3. Фильтр: без ?, без category_filter, slug >= 6 символов
            if "?" in path or "category_filter" in path:
                continue
            parts = [p for p in path.split("/") if p]
            if len(parts) < 2:
                continue
            slug = parts[1] if len(parts) > 1 else ""
            if len(slug) < 6:
                continue
            full_url = base + path if path.startswith("/") else base + "/" + path
            if full_url not in seen:
                seen.add(full_url)
                links.append(full_url)

        # 4. До 20 уникальных URL статей
        articles: list[dict] = []
        for url in links[:20]:
            try:
                await asyncio.sleep(random.uniform(0.8, 2.0))
                r = await client.get(url)
                r.raise_for_status()
                s = BeautifulSoup(r.text, "html.parser")
                title_el = s.find("h1")
                title = title_el.get_text(strip=True) if title_el else ""
                content_div = (
                    s.find("div", class_=lambda c: c and "article" in (c or "").lower())
                    or s.find("article")
                    or s.find("div", class_=lambda c: c and "content" in (c or "").lower())
                )
                content = content_div.get_text(separator="\n", strip=True) if content_div else ""
                if title and content:
                    articles.append({"url": url, "title": title, "content": content})
            except Exception as e:
                logger.error(f"RBC Companies article fetch error {url}: {e}")

        logger.info(f"RBC Companies: {len(articles)} articles from {profile_url}")
        return articles


async def fetch_links_from_page(url: str) -> List[str]:
    """
    Fetch all article links from a page (HTML or RSS/XML feed).
    
    Args:
        url: URL of the page to parse
        
    Returns:
        List of article URLs found on the page
    """
    # 1. Получаем контент через httpx
    try:
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}
        ) as client:
            response = await client.get(url)
            content = response.text
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return []

    # 2. Если RSS/XML — парсим через xml.etree.ElementTree
    if "<?xml" in content[:100] or "rss" in url.lower() or "feed" in url.lower():
        try:
            root = ET.fromstring(content)
            links = []
            for item in root.iter("item"):
                link_el = item.find("link")
                if link_el is not None and link_el.text:
                    links.append(link_el.text.strip())
            logger.info(f"RSS parsed {len(links)} links from {url}")
            return links
        except Exception as e:
            logger.error(f"RSS parse error for {url}: {e}")
            return []

    # 3. Иначе — HTML логика
    try:
        soup = BeautifulSoup(content, "html.parser")
        links = []

        for link in soup.find_all("a", href=True):
            href = link["href"]

            if not href.startswith("http"):
                href = urljoin(url, href)

            parsed = urlparse(href)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                if any(skip in href.lower() for skip in ["#", "javascript:", "mailto:", "tel:"]):
                    continue

                links.append(href)

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
