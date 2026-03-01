import asyncio
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from core.config import settings


class SEOWriter:
    """Генерирует SEO-оптимизированные статьи на основе анализа контента."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
        )

    async def write(
        self,
        analysis: str,
        tone: str,
        keywords: list[str] | None = None,
        llm_model: str = "anthropic/claude-3-5-sonnet",
    ) -> str:
        """
        Пишет полноценную SEO-статью в формате Markdown.

        Args:
            analysis: Результат анализа контента конкурента
            tone: Тон статьи (например, "профессиональный", "дружелюбный", "экспертный")
            keywords: Список SEO-ключевых слов для органичного использования
            llm_model: Модель LLM для генерации (по умолчанию Claude 3.5 Sonnet)

        Returns:
            Готовая SEO-статья в формате Markdown

        Raises:
            RuntimeError: Если не удалось сгенерировать статью после 3 попыток
        """
        keywords_str = ", ".join(keywords) if keywords else "не заданы"

        system_prompt = (
            "Ты профессиональный SEO-копирайтер и SMM-специалист. "
            "Напиши полноценную SEO-статью в формате Markdown. "
            "Обязательная структура: H1-заголовок, вступление (2-3 предложения), "
            "3-5 разделов с H2/H3, списки и выделения, заключение с CTA. "
            f"Tone of Voice: {tone}. Длина: не менее 2000 символов. "
            f"Ключевые слова (использовать органично): {keywords_str}."
        )

        user_prompt = (
            "Ниже представлен анализ статьи конкурента. "
            "Используй его как основу для создания более сильной статьи:\n\n"
            f"{analysis}"
        )

        for attempt in range(3):
            try:
                logger.info(
                    "Writing SEO article: model={} tone='{}' keywords_count={} attempt={}/3",
                    llm_model,
                    tone,
                    len(keywords) if keywords else 0,
                    attempt + 1,
                )

                response = await self.client.chat.completions.create(
                    model=llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.8,
                )

                article = self._extract_text(response)
                logger.success(
                    "SEO article generated: length={} chars",
                    len(article),
                )
                return article

            except Exception as exc:
                if attempt == 2:
                    logger.error(
                        "Failed to write SEO article after 3 attempts: model={} error={}",
                        llm_model,
                        exc,
                    )
                    raise RuntimeError(f"Article writing failed: {exc}") from exc

                delay = 2**attempt
                logger.warning(
                    "Article writing attempt {}/3 failed: {}. Retry in {} sec.",
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError("Failed to write SEO article after 3 attempts")

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
