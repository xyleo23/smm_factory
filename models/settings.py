from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    tone: Mapped[str] = mapped_column(String(128), default="Экспертный", nullable=False)
    is_auto_publish: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parse_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    serp_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_template: Mapped[str | None] = mapped_column(String(512), nullable=True)
    internal_links: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_llm: Mapped[str] = mapped_column(
        String(255), default="anthropic/claude-3-5-sonnet", nullable=False
    )
    tg_channels: Mapped[str | None] = mapped_column(Text, nullable=True)
