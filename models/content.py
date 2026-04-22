"""Data models for the content workflow pipeline."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ContentStatus(str, Enum):
    IDEA = "idea"
    DRAFTING = "drafting"
    OPTIMIZING = "optimizing"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"


class Platform(str, Enum):
    XIAOHONGSHU = "xiaohongshu"
    WECHAT = "wechat"
    DOUYIN = "douyin"
    BILIBILI = "bilibili"
    ZHIHU = "zhihu"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    JIKE = "jike"
    THREADS = "threads"


class ContentType(str, Enum):
    TEXT_IMAGE = "text_image"
    SHORT_VIDEO = "short_video"
    LONG_VIDEO = "long_video"
    THREAD = "thread"
    ARTICLE = "article"


@dataclass
class ContentIdea:
    """A topic idea generated during research phase."""

    topic: str
    angle: str  # 切入角度
    keywords: list[str] = field(default_factory=list)
    trending_score: float = 0.0  # 0-1, how trending the topic is
    competition_score: float = 0.0  # 0-1, how competitive (lower = better)
    target_platforms: list[Platform] = field(default_factory=list)
    source: str = ""  # where the idea came from
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentDraft:
    """A content draft generated from an idea."""

    idea: ContentIdea
    title: str = ""
    body: str = ""
    tags: list[str] = field(default_factory=list)
    cover_image_prompt: str = ""  # prompt for AI image generation
    image_prompts: list[str] = field(default_factory=list)
    content_type: ContentType = ContentType.TEXT_IMAGE
    platform: Platform = Platform.XIAOHONGSHU
    status: ContentStatus = ContentStatus.DRAFTING
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "cover_image_prompt": self.cover_image_prompt,
            "image_prompts": self.image_prompts,
            "content_type": self.content_type.value,
            "platform": self.platform.value,
            "status": self.status.value,
            "topic": self.idea.topic,
            "angle": self.idea.angle,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ContentFinal:
    """Final content ready for publishing."""

    draft: ContentDraft
    title: str = ""
    body: str = ""
    tags: list[str] = field(default_factory=list)
    cover_image_url: str = ""
    image_urls: list[str] = field(default_factory=list)
    quality_score: float = 0.0  # 0-1
    quality_feedback: str = ""
    platform: Platform = Platform.XIAOHONGSHU
    status: ContentStatus = ContentStatus.REVIEWING
    feishu_doc_url: str = ""
    published_url: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "cover_image_url": self.cover_image_url,
            "image_urls": self.image_urls,
            "quality_score": self.quality_score,
            "quality_feedback": self.quality_feedback,
            "platform": self.platform.value,
            "status": self.status.value,
            "feishu_doc_url": self.feishu_doc_url,
            "published_url": self.published_url,
            "created_at": self.created_at.isoformat(),
            "draft": self.draft.to_dict(),
        }
