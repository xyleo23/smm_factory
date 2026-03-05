import asyncio
import re
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from core.config import settings


def _seo_api_key() -> str | None:
    return getattr(settings, "openrouter_api_key", None) or getattr(
        settings, "OPENROUTER_API_KEY", None
    )


class SEOChecker:
    """Проверяет SEO-качество сгенерированных статей и коротких постов."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=_seo_api_key() or "",
        )
        self.model = "openai/gpt-4o-mini"

    @classmethod
    async def check(cls, text: str, keywords: list[str] | None = None) -> dict:
        """Проверяет текст. Для коротких постов (<1200 символов) — мягкие критерии."""
        instance = cls()
        return await instance._check_impl(text, keywords)

    async def _check_impl(
        self,
        text: str,
        keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Проверяет SEO-качество текста и возвращает метрики.

        Args:
            text: Текст статьи для проверки
            keywords: Список ключевых слов для проверки плотности

        Returns:
            Словарь с метриками:
            - score: int (0-100) - общий SEO-рейтинг
            - has_h1: bool - наличие H1 заголовка
            - has_h2: bool - наличие H2 заголовков
            - length: int - длина текста в символах
            - keyword_density: float - плотность ключевых слов (%)
            - issues: list[str] - список выявленных проблем
            - passed: bool - прошла ли проверку (score >= 70)
        """
        # Базовые проверки структуры
        has_h1 = bool(re.search(r"^#\s+.+", text, re.MULTILINE))
        has_h2 = bool(re.search(r"^##\s+.+", text, re.MULTILINE))
        length = len(text)
        is_short_post = length < 1200

        # Проверка плотности ключевых слов
        keyword_density = 0.0
        if keywords:
            text_lower = text.lower()
            keyword_count = sum(text_lower.count(kw.lower()) for kw in keywords)
            words_count = len(text.split())
            keyword_density = (keyword_count / words_count * 100) if words_count > 0 else 0.0

        # Сбор проблем (для коротких постов — другие критерии)
        issues: list[str] = []
        if is_short_post:
            if length < 200:
                issues.append(f"Пост слишком короткий: {length} символов")
            if keywords and keyword_density < 0.3:
                issues.append(f"Низкая плотность ключевых слов: {keyword_density:.2f}%")
        else:
            if not has_h1:
                issues.append("Отсутствует H1 заголовок")
            if not has_h2:
                issues.append("Отсутствуют H2 заголовки")
            if length < 2000:
                issues.append(f"Статья слишком короткая: {length} символов (минимум 2000)")
            if keywords and keyword_density < 0.5:
                issues.append(f"Низкая плотность ключевых слов: {keyword_density:.2f}%")

        # Запрашиваем оценку у LLM (для коротких постов — упрощённая оценка)
        score = await self._get_llm_score(text, keywords, is_short_post)

        if not is_short_post:
            if not has_h1:
                score = max(0, score - 20)
            if not has_h2:
                score = max(0, score - 15)
            if length < 2000:
                score = max(0, score - 10)

        passed = score >= 70

        result = {
            "score": score,
            "has_h1": has_h1,
            "has_h2": has_h2,
            "length": length,
            "keyword_density": keyword_density,
            "issues": issues,
            "passed": passed,
        }

        if not passed:
            logger.warning(
                "SEO check failed: score={} issues={}",
                score,
                issues,
            )
        else:
            logger.success(
                "SEO check passed: score={} length={} keyword_density={:.2f}%",
                score,
                length,
                keyword_density,
            )

        return result

    async def _get_llm_score(
        self, text: str, keywords: list[str] | None, is_short_post: bool = False
    ) -> int:
        """Получает SEO-оценку от LLM (0-100)."""
        keywords_str = ", ".join(keywords) if keywords else "не заданы"

        if is_short_post:
            prompt = (
                "Оцени качество короткого поста для Telegram по шкале 0–100. "
                "Учитывай читабельность, информативность, русский язык. "
                f"Ключевые слова: {keywords_str}.\n\n"
                "Верни ТОЛЬКО число 0–100.\n\n"
                f"Текст:\n{text[:1500]}"
            )
        else:
            prompt = (
                "Оцени SEO-качество следующей статьи по шкале от 0 до 100. "
                "Учитывай структуру, читабельность, информативность, CTA. "
                f"Ключевые слова для проверки: {keywords_str}.\n\n"
                "Верни ТОЛЬКО число от 0 до 100, без дополнительного текста.\n\n"
                f"Текст статьи:\n{text[:3000]}"
            )

        for attempt in range(3):
            try:
                logger.debug("Requesting LLM SEO score, attempt {}/3", attempt + 1)

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=10,
                )

                score_text = self._extract_text(response)
                # Извлекаем первое число из ответа
                match = re.search(r"\b(\d+)\b", score_text)
                if match:
                    score = int(match.group(1))
                    score = max(0, min(100, score))  # Ограничиваем диапазон 0-100
                    logger.debug("LLM SEO score: {}", score)
                    return score

                logger.warning("LLM returned non-numeric score: '{}'", score_text)
                return 50  # Возвращаем среднее значение по умолчанию

            except Exception as exc:
                if attempt == 2:
                    logger.error("Failed to get LLM SEO score after 3 attempts: {}", exc)
                    return 50  # Возвращаем среднее значение при ошибке

                delay = 2**attempt
                logger.warning(
                    "LLM score attempt {}/3 failed: {}. Retry in {} sec.",
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        return 50

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
