"""Content optimization module."""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from config.prompts.optimization import CONTENT_OPTIMIZATION_PROMPT
from core.pipeline import PipelineStep
from models.content import ContentDraft, ContentStatus

logger = logging.getLogger(__name__)


class ContentOptimizationStep(PipelineStep):
    """Pipeline step that optimizes draft content for the target platform.

    Input context:
        - draft: ContentDraft

    Output context (modified):
        - draft: ContentDraft (updated with optimized content)
        - optimization_changes: list[str]
    """

    def __init__(self, ai: AIClient, max_rounds: int = 1):
        self.ai = ai
        self.max_rounds = max_rounds

    def validate(self, context: dict[str, Any]) -> bool:
        return "draft" in context

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        draft: ContentDraft = context["draft"]
        all_changes = []

        for round_num in range(self.max_rounds):
            logger.info("Optimization round %d/%d", round_num + 1, self.max_rounds)

            prompt = CONTENT_OPTIMIZATION_PROMPT.format(
                title=draft.title,
                body=draft.body,
                tags=", ".join(draft.tags),
            )

            data = self.ai.chat_json(
                prompt,
                system="你是一位小红书内容优化专家。请始终返回有效的JSON。",
                temperature=0.5,
            )

            # Update draft with optimized content
            draft.title = data.get("title", draft.title)
            draft.body = data.get("body", draft.body)
            draft.tags = data.get("tags", draft.tags)
            draft.status = ContentStatus.OPTIMIZING

            changes = data.get("changes", [])
            all_changes.extend(changes)

            logger.info("Optimization changes: %s", changes)

        draft.status = ContentStatus.REVIEWING
        context["draft"] = draft
        context["optimization_changes"] = all_changes
        return context
