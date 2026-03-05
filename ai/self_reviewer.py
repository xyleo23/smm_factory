import asyncio
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from core.config import settings


def _reviewer_api_key() -> str | None:
    return getattr(settings, "openrouter_api_key", None) or getattr(
        settings, "OPENROUTER_API_KEY", None
    )


class SelfReviewer:
    """Самостоятельно проверяет и улучшает сгенерированные тексты."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=_reviewer_api_key() or "",
        )
        self.model = "anthropic/claude-3-5-sonnet"

    @classmethod
    async def review(cls, text: str, issues: list[str]) -> str:
        instance = cls()
        return await instance._review_impl(text, issues)

    async def _review_impl(self, text: str, issues: list[str]) -> str:
        """
        Проверяет текст и устраняет выявленные проблемы.

        Args:
            text: Исходный текст статьи
            issues: Список проблем, которые нужно устранить

        Returns:
            Улучшенная версия текста (или исходный текст, если issues пустой)

        Raises:
            RuntimeError: Если не удалось выполнить ревью после 3 попыток
        """
        # Экономия токенов: если проблем нет, возвращаем текст без запроса к API
        if not issues:
            logger.info("No issues to review, returning original text")
            return text

        issues_text = "\n".join(f"- {issue}" for issue in issues)

        system_prompt = (
            "Ты строгий редактор. Устрани следующие проблемы в тексте:\n"
            f"{issues_text}\n\n"
            "Убери воду, добавь конкретику. Сохрани Markdown-структуру и тон."
        )

        user_prompt = f"Исходный текст:\n\n{text}"

        for attempt in range(3):
            try:
                logger.info(
                    "Reviewing text: issues_count={} text_length={} attempt={}/3",
                    len(issues),
                    len(text),
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

                reviewed_text = self._extract_text(response)
                logger.success(
                    "Text review completed: original_length={} reviewed_length={}",
                    len(text),
                    len(reviewed_text),
                )
                return reviewed_text

            except Exception as exc:
                if attempt == 2:
                    logger.error(
                        "Failed to review text after 3 attempts: issues_count={} error={}",
                        len(issues),
                        exc,
                    )
                    raise RuntimeError(f"Text review failed: {exc}") from exc

                delay = 2**attempt
                logger.warning(
                    "Text review attempt {}/3 failed: {}. Retry in {} sec.",
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError("Failed to review text after 3 attempts")

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
