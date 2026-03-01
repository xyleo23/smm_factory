import asyncio
from typing import Any

import aiohttp
from loguru import logger

from core.config import settings


class NanoBananaGenerator:
    """Генерирует изображения для SMM-статей через Nano Banana 2 API."""

    API_URL = "https://api.nanobanana.com/v2/generate"

    def __init__(self) -> None:
        self.api_key = settings.NANO_BANANA_API_KEY

    async def generate(self, title: str, topic: str) -> str | None:
        """
        Генерирует SMM-баннер для статьи.

        Args:
            title: Заголовок статьи (будет размещен на баннере)
            topic: Тема статьи для контекста генерации

        Returns:
            URL сгенерированного изображения или None при ошибке

        Note:
            Если NANO_BANANA_API_KEY не задан, возвращает None с WARNING в логах
        """
        if not self.api_key or self.api_key.strip() == "":
            logger.warning(
                "NANO_BANANA_API_KEY not configured, skipping image generation"
            )
            return None

        prompt = (
            f"Яркий SMM-баннер для статьи. Тема: {topic}. "
            f"Текст на баннере: '{title}'. "
            "Стиль: современный, градиент, профессиональный дизайн. "
            "Кириллица, русский язык."
        )

        payload = {
            "prompt": prompt,
            "width": 1200,
            "height": 630,
            "steps": 30,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(3):
            try:
                logger.info(
                    "Generating image: title='{}' topic='{}' attempt={}/3",
                    title[:50],
                    topic[:50],
                    attempt + 1,
                )

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.API_URL,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as response:
                        if response.status == 401:
                            logger.error("Invalid Nano Banana API key")
                            return None

                        if response.status == 429:
                            delay = 2**attempt
                            logger.warning(
                                "Rate limit (429) from Nano Banana API, retry in {} sec",
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue

                        if response.status >= 400:
                            body = await response.text()
                            logger.error(
                                "Nano Banana API error: status={} body={}",
                                response.status,
                                body,
                            )
                            raise RuntimeError(
                                f"Nano Banana API error {response.status}: {body}"
                            )

                        data = await response.json()
                        image_url = self._extract_image_url(data)

                        if not image_url:
                            logger.error(
                                "Failed to extract image URL from response: {}",
                                data,
                            )
                            raise RuntimeError("No image URL in Nano Banana response")

                        logger.success(
                            "Image generated successfully: url={}",
                            image_url,
                        )
                        return image_url

            except asyncio.TimeoutError:
                logger.warning(
                    "Nano Banana API timeout on attempt {}/3",
                    attempt + 1,
                )
                if attempt == 2:
                    logger.error("Image generation timed out after 3 attempts")
                    return None

            except Exception as exc:
                if attempt == 2:
                    logger.error(
                        "Failed to generate image after 3 attempts: title='{}' error={}",
                        title[:50],
                        exc,
                    )
                    return None

                delay = 2**attempt
                logger.warning(
                    "Image generation attempt {}/3 failed: {}. Retry in {} sec.",
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        return None

    @staticmethod
    def _extract_image_url(data: dict[str, Any]) -> str | None:
        """
        Извлекает URL изображения из ответа API.

        Поддерживает различные форматы ответа:
        - {"url": "..."}
        - {"image_url": "..."}
        - {"data": {"url": "..."}}
        - {"result": {"url": "..."}}
        """
        # Прямой URL
        if "url" in data and isinstance(data["url"], str):
            return data["url"]

        # image_url
        if "image_url" in data and isinstance(data["image_url"], str):
            return data["image_url"]

        # Вложенные структуры
        for key in ["data", "result", "output"]:
            if key in data and isinstance(data[key], dict):
                nested = data[key]
                if "url" in nested and isinstance(nested["url"], str):
                    return nested["url"]
                if "image_url" in nested and isinstance(nested["image_url"], str):
                    return nested["image_url"]

        # Массив изображений
        if "images" in data and isinstance(data["images"], list) and data["images"]:
            first_image = data["images"][0]
            if isinstance(first_image, str):
                return first_image
            if isinstance(first_image, dict) and "url" in first_image:
                return first_image["url"]

        return None
