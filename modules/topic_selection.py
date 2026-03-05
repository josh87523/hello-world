"""从选题库挑选爆款笔记的 Pipeline Step，替代原 TopicResearchStep。"""

from __future__ import annotations

import logging
from typing import Any

from core.pipeline import PipelineStep
from models.content import ContentIdea, Platform
from modules.topic_bank import TopicBank

logger = logging.getLogger(__name__)


class TopicSelectionStep(PipelineStep):
    """从选题库挑选爆款笔记，注入 context 供下游二创使用。

    Input context:
        - platform: Platform
        - domains: list[str]
        - topic_bank: TopicBank 实例
        - custom_topic: optional str (如果指定则跳过选题库)

    Output context (added):
        - idea: ContentIdea
        - source_note: ScrapedNote (原始爆款笔记)
        - all_ideas: list[ContentIdea]
        - topic_outline: dict
    """

    def __init__(self, topic_bank: TopicBank):
        self.topic_bank = topic_bank

    def validate(self, context: dict[str, Any]) -> bool:
        if context.get("custom_topic"):
            return True
        if self.topic_bank.get_unused_count() == 0:
            logger.error("选题库为空或所有选题已使用，请先 ingest 对标笔记")
            return False
        return True

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        platform: Platform = context["platform"]
        domains: list[str] = context["domains"]

        # 兼容旧模式：指定 topic 时走手动路径
        if context.get("custom_topic"):
            idea = ContentIdea(
                topic=context["custom_topic"],
                angle="用户指定话题",
                keywords=domains,
                target_platforms=[platform],
                source="user_input",
            )
            context["idea"] = idea
            context["all_ideas"] = [idea]
            context["topic_outline"] = {}
            return context

        # 从选题库挑选
        entries = self.topic_bank.select_topic(
            strategy="viral_unused",
            count=1,
        )
        entry = entries[0]
        note = entry.note

        # 构建 ContentIdea
        idea = ContentIdea(
            topic=note.title,
            angle=f"基于爆款笔记二创 (互动量: {note.total_interactions})",
            keywords=note.tags[:5] if note.tags else domains,
            trending_score=min(note.total_interactions / 10000, 1.0),
            competition_score=0.3,
            target_platforms=[platform],
            source="topic_bank",
            metadata={
                "source_note_id": note.note_id,
                "source_author": note.author_name,
                "original_likes": note.likes,
                "original_saves": note.saves,
                "save_like_ratio": note.save_like_ratio,
            },
        )

        # 从原文提取大纲
        paragraphs = [p.strip() for p in note.body.split("\n") if p.strip()]
        outline = {
            "titles": [note.title],
            "outline": paragraphs[:5],
            "structure": "基于爆款原文结构",
            "save_trigger": f"原文收藏数: {note.saves}",
        }

        # 标记已使用
        self.topic_bank.mark_used(note.note_id, idea.id)

        logger.info(
            "Selected from topic bank: '%s' (interactions=%d, save_ratio=%.2f)",
            note.title,
            note.total_interactions,
            note.save_like_ratio,
        )

        context["idea"] = idea
        context["source_note"] = note
        context["all_ideas"] = [idea]
        context["topic_outline"] = outline
        return context
