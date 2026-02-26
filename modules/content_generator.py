"""Content generation module - enhanced with viral formula prompts."""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from config.prompts.content_generation import (
    format_generic_content_prompt,
    format_xhs_content_prompt,
)
from core.pipeline import PipelineStep
from models.content import ContentDraft, ContentIdea, ContentType, Platform

logger = logging.getLogger(__name__)


class ContentGenerationStep(PipelineStep):
    """Pipeline step that generates content from a topic idea.

    Enhanced with:
    - Viral formula injection (save optimization, anti-AI, content structure)
    - Account persona tone customization
    - Save trigger awareness from topic refinement

    Input context:
        - idea: ContentIdea
        - topic_outline: dict
        - platform: Platform
        - domains: list[str]
        - account_tone: optional str
        - account_vertical: optional str

    Output context (added):
        - draft: ContentDraft
    """

    def __init__(self, ai: AIClient):
        self.ai = ai

    def validate(self, context: dict[str, Any]) -> bool:
        return "idea" in context

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        idea: ContentIdea = context["idea"]
        outline = context.get("topic_outline", {})
        platform: Platform = context["platform"]
        domains: list[str] = context["domains"]
        tone: str = context.get("account_tone", "友好专业")

        titles = outline.get("titles", [idea.topic])
        title = titles[0] if titles else idea.topic
        save_trigger = outline.get("save_trigger", "")

        if platform == Platform.XIAOHONGSHU:
            prompt = format_xhs_content_prompt(
                title=title,
                angle=idea.angle,
                keywords="、".join(idea.keywords),
                outline="\n".join(f"- {p}" for p in outline.get("outline", [])),
                domains="、".join(domains),
                tone=tone,
                save_trigger=save_trigger,
            )
        else:
            prompt = format_generic_content_prompt(
                title=title,
                angle=idea.angle,
                keywords="、".join(idea.keywords),
                platform=platform.value,
                domains="、".join(domains),
            )

        logger.info("Generating content for: %s (tone: %s)", title, tone)

        data = self.ai.chat_json(
            prompt,
            system=(
                f"你是一位顶级小红书内容创作者，人设是「{tone}」。"
                "你写的内容必须像真人写的，绝对不能有AI感。请始终返回有效的JSON。"
            ),
            temperature=0.8,
        )

        draft = ContentDraft(
            idea=idea,
            title=data.get("title", title),
            body=data.get("body", ""),
            tags=data.get("tags", []),
            cover_image_prompt=data.get("cover_image_prompt", ""),
            image_prompts=data.get("image_prompts", []),
            content_type=ContentType.TEXT_IMAGE,
            platform=platform,
            metadata={
                "save_hook": data.get("save_hook", ""),
                "tone": tone,
            },
        )

        logger.info("Draft generated: '%s' (%d chars)", draft.title, len(draft.body))
        context["draft"] = draft
        return context
