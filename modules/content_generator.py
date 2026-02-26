"""Content generation module."""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from config.prompts.content_generation import XIAOHONGSHU_CONTENT_PROMPT, GENERIC_CONTENT_PROMPT
from core.pipeline import PipelineStep
from models.content import ContentDraft, ContentIdea, ContentType, Platform

logger = logging.getLogger(__name__)

# Map platform to content prompt template
PLATFORM_PROMPTS = {
    Platform.XIAOHONGSHU: XIAOHONGSHU_CONTENT_PROMPT,
    # Future: add more platform-specific prompts here
}


class ContentGenerationStep(PipelineStep):
    """Pipeline step that generates content from a topic idea.

    Input context:
        - idea: ContentIdea
        - topic_outline: dict
        - platform: Platform
        - domains: list[str]

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

        prompt_template = PLATFORM_PROMPTS.get(platform, GENERIC_CONTENT_PROMPT)

        # Build the best title from outline or idea
        titles = outline.get("titles", [idea.topic])
        title = titles[0] if titles else idea.topic

        prompt = prompt_template.format(
            title=title,
            angle=idea.angle,
            keywords="、".join(idea.keywords),
            outline="\n".join(f"- {p}" for p in outline.get("outline", [])),
            domains="、".join(domains),
            platform=platform.value,
        )

        logger.info("Generating content for: %s", title)

        data = self.ai.chat_json(
            prompt,
            system="你是一位顶级自媒体内容创作者。请始终返回有效的JSON。",
            temperature=0.8,  # slightly more creative for content
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
        )

        logger.info("Draft generated: '%s' (%d chars)", draft.title, len(draft.body))
        context["draft"] = draft
        return context
