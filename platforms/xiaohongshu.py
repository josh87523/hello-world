"""Xiaohongshu (Little Red Book) platform adapter."""

from __future__ import annotations

import logging
from typing import Any

from models.content import ContentFinal, Platform
from platforms.base import PlatformAdapter

logger = logging.getLogger(__name__)

# Xiaohongshu content constraints
XHS_TITLE_MAX_LENGTH = 20
XHS_BODY_MAX_LENGTH = 1000  # characters
XHS_BODY_MIN_LENGTH = 100
XHS_MAX_TAGS = 10
XHS_MAX_IMAGES = 9


class XiaohongshuAdapter(PlatformAdapter):
    """Adapter for publishing to Xiaohongshu.

    Note: Xiaohongshu does not have an official public API.
    The publish() method formats content for manual posting or
    integration with third-party tools.
    """

    @property
    def platform(self) -> Platform:
        return Platform.XIAOHONGSHU

    def format_content(self, content: ContentFinal) -> dict[str, Any]:
        """Format content for Xiaohongshu posting."""
        # Ensure title is within limits
        title = content.title[:XHS_TITLE_MAX_LENGTH]

        # Ensure tags are formatted with #
        tags = []
        for tag in content.tags[:XHS_MAX_TAGS]:
            tag = tag.strip()
            if not tag.startswith("#"):
                tag = f"#{tag}"
            tags.append(tag)

        # Append tags to body
        body = content.body
        tag_line = " ".join(tags)
        formatted_body = f"{body}\n\n{tag_line}"

        return {
            "platform": "xiaohongshu",
            "title": title,
            "body": formatted_body,
            "body_raw": body,
            "tags": tags,
            "images": content.image_urls[:XHS_MAX_IMAGES],
            "cover_image": content.cover_image_url,
        }

    def validate_content(self, content: ContentFinal) -> list[str]:
        """Validate content against Xiaohongshu rules."""
        errors = []

        if not content.title:
            errors.append("标题不能为空")
        elif len(content.title) > XHS_TITLE_MAX_LENGTH:
            errors.append(f"标题超过{XHS_TITLE_MAX_LENGTH}字限制: {len(content.title)}字")

        if not content.body:
            errors.append("正文不能为空")
        elif len(content.body) < XHS_BODY_MIN_LENGTH:
            errors.append(f"正文太短（最少{XHS_BODY_MIN_LENGTH}字）: {len(content.body)}字")

        if len(content.tags) > XHS_MAX_TAGS:
            errors.append(f"标签超过{XHS_MAX_TAGS}个限制")

        return errors

    def publish(self, content: ContentFinal) -> dict[str, Any]:
        """Prepare content for Xiaohongshu publishing.

        Since XHS has no official API, this formats the content
        for manual publishing or third-party tool integration.
        """
        errors = self.validate_content(content)
        if errors:
            return {"success": False, "errors": errors}

        formatted = self.format_content(content)

        logger.info("Content formatted for Xiaohongshu: '%s'", formatted["title"])

        return {
            "success": True,
            "formatted_content": formatted,
            "instructions": (
                "小红书暂无官方API，请通过以下方式发布：\n"
                "1. 复制标题和正文到小红书App\n"
                "2. 上传配图\n"
                "3. 添加话题标签\n"
                "4. 发布"
            ),
        }

    def get_platform_rules(self) -> dict[str, Any]:
        return {
            "title_max_length": XHS_TITLE_MAX_LENGTH,
            "body_max_length": XHS_BODY_MAX_LENGTH,
            "body_min_length": XHS_BODY_MIN_LENGTH,
            "max_tags": XHS_MAX_TAGS,
            "max_images": XHS_MAX_IMAGES,
            "supported_content_types": ["text_image"],
            "best_posting_times": ["07:00-09:00", "12:00-14:00", "18:00-22:00"],
            "tips": [
                "标题含emoji转化率更高",
                "前3行决定是否展开阅读",
                "封面图比例建议3:4",
                "发布后30分钟内回复评论有助于推荐",
            ],
        }
