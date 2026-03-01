"""SQLAlchemy database models for SMM Factory."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Source(Base):
    """Content source for parsing articles."""
    
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_parsed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<Source(id={self.id}, name='{self.name}', url='{self.url}')>"


class UserSettings(Base):
    """User settings for content generation and publishing."""
    
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    
    # Parsing settings
    serp_keywords = Column(JSON, default=list, nullable=False)
    internal_links = Column(JSON, default=list, nullable=False)
    utm_template = Column(String(500), default="?utm_source=auto&utm_medium=post", nullable=False)
    
    # AI settings
    tone = Column(String(100), default="professional", nullable=False)
    keywords = Column(JSON, default=list, nullable=False)
    selected_llm = Column(String(50), default="gpt-4", nullable=False)
    
    # Publishing settings
    tg_channels = Column(JSON, default=list, nullable=False)
    is_auto_publish = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id}, auto_publish={self.is_auto_publish})>"


class Article(Base):
    """Parsed article from content sources."""
    
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    source_id = Column(Integer, nullable=True)
    
    is_processed = Column(Boolean, default=False, nullable=False, index=True)
    parsed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title}', processed={self.is_processed})>"


class Post(Base):
    """Generated content ready for publishing."""
    
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, nullable=True)
    
    title = Column(String(500), nullable=True)
    text = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    
    status = Column(String(50), default="pending", nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    published_at = Column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<Post(id={self.id}, status='{self.status}', title='{self.title}')>"


class ParsingHistory(Base):
    """History of parsing attempts for tracking failures."""
    
    __tablename__ = "parsing_history"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<ParsingHistory(url='{self.url}', status='{self.status}')>"
