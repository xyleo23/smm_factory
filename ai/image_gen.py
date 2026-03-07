"""Генерация изображений для постов — заглушка NanaBananaGenerator."""


class NanaBananaGenerator:
    """Placeholder — будет реализован позже через NanaBanana API."""

    RBC_IMAGE_SUFFIX = (
        " Neutral background, abstract shapes, no text, no letters, "
        "no prices, no logos, specific social network brand colors"
    )

    @classmethod
    def build_image_prompt(
        cls, title: str = "", topic: str = "", target_platform: str = "vc"
    ) -> str:
        """Формирует промпт для генерации изображения с учётом площадки."""
        base = f"{title} {topic}".strip() or "abstract business"
        if target_platform == "rbc":
            base += cls.RBC_IMAGE_SUFFIX
        return base

    @classmethod
    async def generate(
        cls, title: str = "", topic: str = "", target_platform: str = "vc"
    ) -> str | None:
        """
        Placeholder — будет реализован позже через NanaBanana API.
        Для РБК промпт дополняется требованиями: нейтральный фон, без текста, цен, логотипов.
        """
        _ = cls.build_image_prompt(title, topic, target_platform)
        return None
