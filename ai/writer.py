"""Post writer for Telegram channels — короткие посты на русском."""

import asyncio
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from core.config import settings


def _api_key() -> str | None:
    """Поддержка snake_case и UPPER_CASE."""
    return getattr(settings, "openrouter_api_key", None) or getattr(
        settings, "OPENROUTER_API_KEY", None
    )


class SEOWriter:
    """Генерирует короткие посты для Telegram на основе анализа контента."""

    def __init__(self) -> None:
        api_key = _api_key()
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key or "",
        )

    @classmethod
    async def write(
        cls,
        *,
        analysis: str,
        tone: str,
        keywords: list[str] | None = None,
        llm: str | None = None,
        llm_model: str | None = None,
        source_url: str | None = None,
    ) -> str:
        """
        Пишет короткий пост для Telegram (500–800 символов, русский язык).

        Args:
            analysis: Результат анализа контента от ContentAnalyzer
            tone: Тон (профессиональный, живой, экспертный и т.д.)
            keywords: SEO-ключи для органичного использования
            llm: Модель LLM (alias для llm_model)
            llm_model: Модель для генерации
            source_url: Ссылка на оригинал — добавляется в конец поста

        Returns:
            Готовый текст поста для Telegram
        """
        model = llm or llm_model or "anthropic/claude-3-5-sonnet"
        instance = cls()
        return await instance._write_impl(analysis, tone, keywords or [], model, source_url)

    async def _write_impl(
        self,
        analysis: str,
        tone: str,
        keywords: list[str],
        llm_model: str,
        source_url: str | None,
    ) -> str:
        keywords_str = ", ".join(keywords) if keywords else "не заданы"

        system_prompt = (
            "Ты SMM-копирайтер. Пиши короткие посты для Telegram-канала. "
            "ПРАВИЛА:\n"
            "- Язык: ТОЛЬКО русский\n"
            "- Длина: 500–800 символов\n"
            "- Формат: 3–5 предложений, один абзац или короткие абзацы\n"
            "- БЕЗ markdown-заголовков (# ## ###), БЕЗ списков типа 'Key Insights', 'Overview'\n"
            "- Тон: профессиональный, живой, подходящий для канала о бизнесе/финансах\n"
            "- Не используй английские шаблоны вроде 'Comprehensive Guide', 'Key Insights'\n"
            f"- Tone of Voice: {tone}\n"
            f"- Ключевые слова (органично): {keywords_str}"
        )

        user_prompt = (
            "По анализу статьи конкурента напиши краткий пост для Telegram.\n\n"
            f"{analysis}"
        )

        for attempt in range(3):
            try:
                logger.info(
                    "Writing post: model={} tone='{}' attempt={}/3",
                    llm_model,
                    tone,
                    attempt + 1,
                )

                response = await self.client.chat.completions.create(
                    model=llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                )

                text = self._extract_text(response)
                if source_url and source_url.strip():
                    text = f"{text.rstrip()}\n\n📎 Оригинал: {source_url}"
                logger.success("Post generated: length={} chars", len(text))
                return text

            except Exception as exc:
                if attempt == 2:
                    logger.error("Failed to write post after 3 attempts: {}", exc)
                    raise RuntimeError(f"Post writing failed: {exc}") from exc
                delay = 2**attempt
                logger.warning("Write attempt {}/3 failed, retry in {}s", attempt + 1, delay)
                await asyncio.sleep(delay)

        raise RuntimeError("Failed to write post after 3 attempts")

    @staticmethod
    def _extract_text(response: Any) -> str:
        message = response.choices[0].message
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            chunks = []
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    chunks.append(chunk.get("text", ""))
                else:
                    t = getattr(chunk, "text", None)
                    if isinstance(t, str):
                        chunks.append(t)
            return "\n".join(c for c in chunks if c).strip()
        return str(content).strip()
