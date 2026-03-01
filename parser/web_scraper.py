import asyncio
import random
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger


class ArticleParser:
    USER_AGENTS: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.3; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/122.0.0.0 Chrome/122.0.0.0 Safari/537.36",
    ]

    async def human_delay(self) -> None:
        await asyncio.sleep(random.uniform(1, 3))

    async def fetch_html(self, url: str) -> str:
        waits = [5, 10, 20]
        timeout = aiohttp.ClientTimeout(total=15)

        for attempt in range(3):
            headers = {"User-Agent": random.choice(self.USER_AGENTS)}

            try:
                await self.human_delay()
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    async with session.get(url) as response:
                        if response.status == 429:
                            wait_seconds = waits[min(attempt, len(waits) - 1)]
                            logger.warning(
                                "429 for {}. Retry {}/3 in {} sec.",
                                url,
                                attempt + 1,
                                wait_seconds,
                            )
                            await asyncio.sleep(wait_seconds)
                            continue

                        response.raise_for_status()
                        html = await response.text()
                        logger.info("Fetched HTML: {} ({} chars)", url, len(html))
                        return html
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == 2:
                    logger.error("Failed to fetch {} after 3 attempts: {}", url, exc)
                    raise
                wait_seconds = waits[min(attempt, len(waits) - 1)]
                logger.warning(
                    "Fetch error for {} (attempt {}/3): {}. Retry in {} sec.",
                    url,
                    attempt + 1,
                    exc,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)

        raise RuntimeError(f"Unable to fetch HTML from {url}")

    def parse_article(self, html: str) -> dict[str, str] | None:
        soup = BeautifulSoup(html, "html.parser")
        title_node = soup.find("h1")
        if not title_node:
            return None

        title = title_node.get_text(strip=True)
        paragraphs: list[str] = []
        for node in soup.find_all("p"):
            text = node.get_text(" ", strip=True)
            if len(text) > 30:
                paragraphs.append(text)

        content = "\n".join(paragraphs)
        if len(content) < 1000:
            return None

        return {"title": title, "content": content}

    async def fetch_links_from_page(self, url: str) -> list[str]:
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        base = urlparse(url)

        found_urls: list[str] = []
        seen: set[str] = set()

        for link in soup.find_all("a"):
            href = link.get("href")
            if not isinstance(href, str) or not href.strip():
                continue

            absolute_url = urljoin(url, href.strip())
            parsed = urlparse(absolute_url)
            if parsed.scheme not in {"http", "https"}:
                continue

            # same domain only
            if parsed.netloc and parsed.netloc != base.netloc:
                continue

            normalized = parsed._replace(fragment="").geturl()
            if normalized in seen:
                continue

            if self._looks_like_article_link(parsed.path):
                seen.add(normalized)
                found_urls.append(normalized)

            if len(found_urls) >= 10:
                break

        logger.info("Found {} candidate links on {}", len(found_urls), url)
        return found_urls

    @staticmethod
    def _looks_like_article_link(path: str) -> bool:
        if "/id/" in path:
            return True

        segments = [segment for segment in path.split("/") if segment]
        if not segments:
            return False

        slug = segments[-1]
        return len(slug) > 20
