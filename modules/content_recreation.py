"""内容二创模块 - 基于选题库中的爆款笔记进行改写创作。"""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from config.prompts.content_recreation import (
    RECREATION_SYSTEM_PROMPT,
    format_recreation_prompt,
)
from core.pipeline import PipelineStep
from models.competitor import ScrapedNote
from models.content import ContentDraft, ContentIdea, ContentType, Platform

logger = logging.getLogger(__name__)


class ContentRecreationStep(PipelineStep):
    """基于选题库中的爆款笔记做二创改写。

    Input context:
        - idea: ContentIdea
        - source_note: ScrapedNote (原始爆款笔记)
        - platform: Platform
        - domains: list[str]
        - account_tone: optional str
        - recreation_guidance: optional str (人工改写指导)

    Output context (added):
        - draft: ContentDraft
    """

    def __init__(self, ai: AIClient):
        self.ai = ai

    def validate(self, context: dict[str, Any]) -> bool:
        if "idea" not in context:
            return False
        if "source_note" not in context:
            logger.error("缺少 source_note，无法进行二创")
            return False
        return True

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        idea: ContentIdea = context["idea"]
        source_note: ScrapedNote = context["source_note"]
        platform: Platform = context["platform"]
        domains: list[str] = context["domains"]
        tone: str = context.get("account_tone", "友好专业")
        guidance: str = context.get("recreation_guidance", "")

        prompt = format_recreation_prompt(
            source_title=source_note.title,
            source_body=source_note.body,
            source_tags=source_note.tags,
            source_stats={
                "likes": source_note.likes,
                "saves": source_note.saves,
                "comments": source_note.comments,
                "save_like_ratio": source_note.save_like_ratio,
            },
            tone=tone,
            domains="、".join(domains),
            guidance=guidance,
        )

        system = RECREATION_SYSTEM_PROMPT.format(tone=tone)

        logger.info(
            "Recreating from: '%s' (likes=%d, saves=%d)",
            source_note.title,
            source_note.likes,
            source_note.saves,
        )

        data = self.ai.chat_json(prompt, system=system, temperature=0.8)

        draft = ContentDraft(
            idea=idea,
            title=data.get("title", ""),
            body=data.get("body", ""),
            tags=data.get("tags", []),
            cover_image_prompt=data.get("cover_image_prompt", ""),
            image_prompts=data.get("image_prompts", []),
            content_type=ContentType.TEXT_IMAGE,
            platform=platform,
            metadata={
                "recreation_type": "rewrite",
                "source_note_id": source_note.note_id,
                "source_author": source_note.author_name,
                "tone": tone,
                "guidance": guidance,
                "save_hook": data.get("save_hook", ""),
                "recreation_analysis": data.get("recreation_analysis", ""),
            },
        )

        logger.info("Recreation draft: '%s' (%d chars)", draft.title, len(draft.body))
        context["draft"] = draft
        return context
