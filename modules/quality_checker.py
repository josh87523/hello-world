"""Quality checking module."""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from config.prompts.optimization import QUALITY_CHECK_PROMPT
from core.pipeline import PipelineStep
from models.content import ContentDraft, ContentFinal, ContentStatus

logger = logging.getLogger(__name__)

# Minimum overall score to pass quality check
QUALITY_THRESHOLD = 0.7


class QualityCheckStep(PipelineStep):
    """Pipeline step that evaluates content quality and produces final output.

    Input context:
        - draft: ContentDraft

    Output context (added):
        - final_content: ContentFinal
        - quality_scores: dict
    """

    def __init__(self, ai: AIClient, threshold: float = QUALITY_THRESHOLD):
        self.ai = ai
        self.threshold = threshold

    def validate(self, context: dict[str, Any]) -> bool:
        return "draft" in context

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        draft: ContentDraft = context["draft"]

        prompt = QUALITY_CHECK_PROMPT.format(
            platform=draft.platform.value,
            title=draft.title,
            body=draft.body,
            tags=", ".join(draft.tags),
        )

        data = self.ai.chat_json(
            prompt,
            system="你是一位严格的内容质量审核员。请始终返回有效的JSON。",
            temperature=0.2,  # more deterministic for evaluation
        )

        scores = data.get("scores", {})
        overall = float(data.get("overall_score", 0))
        passed = data.get("pass", overall >= self.threshold)
        feedback = data.get("feedback", "")

        logger.info(
            "Quality check: overall=%.2f, pass=%s, feedback=%s",
            overall,
            passed,
            feedback[:100],
        )

        # Build final content
        final = ContentFinal(
            draft=draft,
            title=draft.title,
            body=draft.body,
            tags=draft.tags,
            quality_score=overall,
            quality_feedback=feedback,
            platform=draft.platform,
            status=ContentStatus.APPROVED if passed else ContentStatus.FAILED,
        )

        context["final_content"] = final
        context["quality_scores"] = scores
        context["quality_passed"] = passed
        return context
