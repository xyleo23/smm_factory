import asyncio
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from core.config import settings


class SMMAgent:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
        )

    async def generate_post(
        self,
        title: str,
        content: str,
        tone: str,
        llm_model: str = "anthropic/claude-3-5-sonnet",
    ) -> str:
        analysis_prompt = (
            "Проанализируй статью конкурента, вытащи 3-4 главных тезиса, "
            "слабые места и ключи.\n\n"
            f"Заголовок: {title}\n\n"
            f"Текст:\n{content}"
        )

        for attempt in range(3):
            try:
                analysis_response = await self.client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[{"role": "user", "content": analysis_prompt}],
                )
                analysis_text = self._extract_text(analysis_response)

                writing_prompt = (
                    "Ты SEO-копирайтер. Напиши уникальную SEO-статью в Markdown.\n"
                    f"Tone: {tone}.\n"
                    "Структура: H1, вступление, 3-5 разделов H2/H3, заключение с CTA.\n"
                    "Длина: 2000+ символов.\n\n"
                    "Ниже анализ материала конкурента, используй его как контекст:\n"
                    f"{analysis_text}"
                )
                article_response = await self.client.chat.completions.create(
                    model=llm_model,
                    messages=[{"role": "user", "content": writing_prompt}],
                )
                return self._extract_text(article_response)
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    logger.error("Failed to generate post after 3 attempts: {}", exc)
                    raise
                delay = 2**attempt
                logger.warning(
                    "generate_post attempt {}/3 failed: {}. Retry in {} sec.",
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError("Failed to generate post")

    @staticmethod
    def _extract_text(response: Any) -> str:
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
