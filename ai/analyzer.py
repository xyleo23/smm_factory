import asyncio
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from core.config import settings


class ContentAnalyzer:
    """Анализирует контент конкурентов и выявляет ключевые тезисы для улучшения."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
        )
        self.model = "openai/gpt-4o-mini"

    async def analyze(self, title: str, content: str) -> str:
        """
        Анализирует статью конкурента и возвращает структурированный анализ.

        Args:
            title: Заголовок статьи
            content: Текст статьи

        Returns:
            Структурированный анализ с тезисами, слабыми местами, SEO-ключами и углом атаки

        Raises:
            RuntimeError: Если не удалось выполнить анализ после 3 попыток
        """
        system_prompt = (
            "Ты опытный SMM-аналитик и SEO-стратег. "
            "Проанализируй статью конкурента. Вытащи:\n"
            "1) 3-4 главных тезиса\n"
            "2) Слабые места и что не раскрыто\n"
            "3) Потенциальные SEO-ключи по теме\n"
            "4) Угол атаки для более сильной статьи\n"
            "Отвечай структурировано, кратко."
        )

        user_prompt = f"Заголовок: {title}\n\nТекст статьи:\n{content}"

        for attempt in range(3):
            try:
                logger.info(
                    "Analyzing content: title='{}' content_length={} attempt={}/3",
                    title[:50],
                    len(content),
                    attempt + 1,
                )

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                )

                analysis = self._extract_text(response)
                logger.success(
                    "Content analysis completed: analysis_length={}",
                    len(analysis),
                )
                return analysis

            except Exception as exc:
                if attempt == 2:
                    logger.error(
                        "Failed to analyze content after 3 attempts: title='{}' error={}",
                        title[:50],
                        exc,
                    )
                    raise RuntimeError(f"Content analysis failed: {exc}") from exc

                delay = 2**attempt
                logger.warning(
                    "Content analysis attempt {}/3 failed: {}. Retry in {} sec.",
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError("Failed to analyze content after 3 attempts")

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Извлекает текст из ответа OpenAI API."""
        message = response.choices[0].message
        content = getattr(message, "content", "")

        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_chunks: list[str] = []
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    text_chunks.append(chunk.get("text", ""))
                else:
                    text_value = getattr(chunk, "text", None)
                    if isinstance(text_value, str):
                        text_chunks.append(text_value)
            return "\n".join(part for part in text_chunks if part).strip()

        return str(content).strip()
