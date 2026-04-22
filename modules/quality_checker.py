"""Quality checking module - enhanced with research-backed scoring.

Key changes from research:
- Threshold raised to 0.75 (from 0.7)
- Added save_potential as a scoring dimension (highest algorithm weight)
- Added hard fail on authenticity < 0.7 (anti-AI is non-negotiable)
- Added hard fail on any dimension < 0.6
"""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from config.prompts.optimization import format_quality_check_prompt
from core.pipeline import PipelineStep
from models.content import ContentDraft, ContentFinal, ContentStatus

logger = logging.getLogger(__name__)

QUALITY_THRESHOLD = 0.75
AUTHENTICITY_FLOOR = 0.7
DIMENSION_FLOOR = 0.6


class QualityCheckStep(PipelineStep):
    """Pipeline step that evaluates content quality with research-backed criteria.

    Enhanced scoring dimensions:
    - hook_score: title + first 3 lines attractiveness
    - save_potential: will users save this? (most important for XHS algo)
    - authenticity_score: human-written feel (hard fail below 0.7)
    - engagement_score: will users comment?
    - value_score: information gain
    - platform_fit_score: XHS format compliance

    Input context:
        - draft: ContentDraft

    Output context (added):
        - final_content: ContentFinal
        - quality_scores: dict
        - quality_passed: bool
    """

    def __init__(self, ai: AIClient, threshold: float = QUALITY_THRESHOLD):
        self.ai = ai
        self.threshold = threshold

    def validate(self, context: dict[str, Any]) -> bool:
        return "draft" in context

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        draft: ContentDraft = context["draft"]

        prompt = format_quality_check_prompt(
            platform=draft.platform.value,
            title=draft.title,
            body=draft.body,
            tags=", ".join(draft.tags),
        )

        data = self.ai.chat_json(
            prompt,
            system="你是一位严格的内容质量审核员。请始终返回有效的JSON。",
            temperature=0.2,
        )

        scores = data.get("scores", {})
        overall = float(data.get("overall_score", 0))
        feedback = data.get("feedback", "")
        failed_dims = data.get("failed_dimensions", [])

        # Apply hard fail rules from research
        authenticity = scores.get("authenticity_score", 0)
        passed = overall >= self.threshold
        fail_reasons = []

        if authenticity < AUTHENTICITY_FLOOR:
            passed = False
            fail_reasons.append(
                f"authenticity_score={authenticity:.2f} < {AUTHENTICITY_FLOOR}"
            )

        for dim_name, dim_score in scores.items():
            if isinstance(dim_score, (int, float)) and dim_score < DIMENSION_FLOOR:
                passed = False
                fail_reasons.append(f"{dim_name}={dim_score:.2f} < {DIMENSION_FLOOR}")

        if not passed and not fail_reasons:
            fail_reasons.append(f"overall_score={overall:.2f} < {self.threshold}")

        logger.info(
            "Quality check: overall=%.2f, pass=%s%s",
            overall,
            passed,
            f", fail_reasons={fail_reasons}" if fail_reasons else "",
        )

        final = ContentFinal(
            draft=draft,
            title=draft.title,
            body=draft.body,
            tags=draft.tags,
            quality_score=overall,
            quality_feedback=feedback,
            platform=draft.platform,
            status=ContentStatus.APPROVED if passed else ContentStatus.FAILED,
            metadata={
                "failed_dimensions": failed_dims,
                "fail_reasons": fail_reasons,
                "cover_variants": context.get("cover_variants", []),
            },
        )

        context["final_content"] = final
        context["quality_scores"] = scores
        context["quality_passed"] = passed
        return context
