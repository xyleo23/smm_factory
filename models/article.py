from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
