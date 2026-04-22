"""Data models for competitor/benchmark account analysis and scraped content."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ScrapedNote:
    """A single note scraped from Xiaohongshu."""

    note_id: str
    title: str
    body: str = ""
    author_id: str = ""
    author_name: str = ""
    likes: int = 0
    saves: int = 0
    comments: int = 0
    shares: int = 0
    views: int = 0
    tags: list[str] = field(default_factory=list)
    cover_url: str = ""
    image_urls: list[str] = field(default_factory=list)
    note_type: str = "text_image"  # text_image / video
    published_at: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    # Calculated
    save_like_ratio: float = 0.0
    total_interactions: int = 0

    def compute_metrics(self) -> None:
        self.save_like_ratio = self.saves / self.likes if self.likes > 0 else 0
        self.total_interactions = self.likes + self.saves + self.comments + self.shares

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "title": self.title,
            "body": self.body,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "likes": self.likes,
            "saves": self.saves,
            "comments": self.comments,
            "shares": self.shares,
            "views": self.views,
            "tags": self.tags,
            "cover_url": self.cover_url,
            "image_urls": self.image_urls,
            "note_type": self.note_type,
            "published_at": self.published_at,
            "scraped_at": self.scraped_at,
            "save_like_ratio": self.save_like_ratio,
            "total_interactions": self.total_interactions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScrapedNote:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CompetitorAccount:
    """A benchmark/competitor account to track and analyze."""

    user_id: str
    nickname: str
    home_url: str = ""
    desc: str = ""
    followers: int = 0
    total_notes: int = 0
    vertical: str = ""  # which vertical this competitor covers
    tags: list[str] = field(default_factory=list)
    # Analysis results
    avg_likes: float = 0
    avg_saves: float = 0
    avg_save_like_ratio: float = 0
    viral_rate: float = 0  # % of notes with 1000+ interactions
    top_note_ids: list[str] = field(default_factory=list)
    posting_frequency: str = ""  # e.g. "2/day", "5/week"
    common_title_patterns: list[str] = field(default_factory=list)
    common_tags: list[str] = field(default_factory=list)
    content_style: str = ""  # AI-generated style summary
    last_scraped: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "home_url": self.home_url,
            "desc": self.desc,
            "followers": self.followers,
            "total_notes": self.total_notes,
            "vertical": self.vertical,
            "tags": self.tags,
            "avg_likes": self.avg_likes,
            "avg_saves": self.avg_saves,
            "avg_save_like_ratio": self.avg_save_like_ratio,
            "viral_rate": self.viral_rate,
            "top_note_ids": self.top_note_ids,
            "posting_frequency": self.posting_frequency,
            "common_title_patterns": self.common_title_patterns,
            "common_tags": self.common_tags,
            "content_style": self.content_style,
            "last_scraped": self.last_scraped,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompetitorAccount:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BenchmarkReport:
    """Analysis report comparing our accounts against competitors."""

    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    competitors: list[CompetitorAccount] = field(default_factory=list)
    top_performing_notes: list[ScrapedNote] = field(default_factory=list)
    # Insights
    title_patterns: list[str] = field(default_factory=list)
    content_patterns: list[str] = field(default_factory=list)
    best_tags: list[str] = field(default_factory=list)
    avg_save_like_ratio: float = 0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "created_at": self.created_at,
            "competitors": [c.to_dict() for c in self.competitors],
            "top_performing_notes": [n.to_dict() for n in self.top_performing_notes],
            "title_patterns": self.title_patterns,
            "content_patterns": self.content_patterns,
            "best_tags": self.best_tags,
            "avg_save_like_ratio": self.avg_save_like_ratio,
            "recommendations": self.recommendations,
        }
