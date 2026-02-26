"""Main content workflow orchestrator - enhanced with matrix and cover support."""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from core.pipeline import Pipeline
from models.content import ContentFinal, Platform

logger = logging.getLogger(__name__)


class ContentWorkflow:
    """Orchestrates the full content creation workflow.

    Enhanced with:
    - Matrix account persona injection (tone, vertical, domains)
    - Cover strategy variant generation
    - Analytics tracking integration

    Usage:
        # Single account mode
        workflow = ContentWorkflow(ai_client=client, platform=Platform.XIAOHONGSHU)
        results = workflow.run(domains=["ai", "创业"], count=3)

        # Matrix mode (with account persona)
        results = workflow.run(
            domains=["ai工具", "效率"],
            count=2,
            account_tone="极客+接地气",
            account_vertical="ai_tools",
            account_id="matrix_01",
        )
    """

    def __init__(
        self,
        ai_client: AIClient,
        platform: Platform = Platform.XIAOHONGSHU,
        feishu_client: Any | None = None,
        cover_variants: int = 3,
    ):
        self.ai = ai_client
        self.platform = platform
        self.feishu = feishu_client
        self.cover_variants = cover_variants

    def build_pipeline(self, include_cover: bool = True) -> Pipeline:
        """Build the full content pipeline with all steps.

        Args:
            include_cover: Whether to include cover variant generation step.
        """
        from modules.content_generator import ContentGenerationStep
        from modules.content_optimizer import ContentOptimizationStep
        from modules.cover_strategy import CoverStrategyStep
        from modules.quality_checker import QualityCheckStep
        from modules.topic_research import TopicResearchStep

        pipeline = Pipeline(name=f"content-{self.platform.value}")
        pipeline.add_step(TopicResearchStep(self.ai))
        pipeline.add_step(ContentGenerationStep(self.ai))
        pipeline.add_step(ContentOptimizationStep(self.ai))
        if include_cover:
            pipeline.add_step(CoverStrategyStep(self.ai, self.cover_variants))
        pipeline.add_step(QualityCheckStep(self.ai))

        return pipeline

    def run(
        self,
        domains: list[str] | None = None,
        count: int = 1,
        custom_topic: str | None = None,
        account_tone: str = "友好专业",
        account_vertical: str = "通用",
        account_id: str = "",
        competitor_context: str = "",
    ) -> list[dict[str, Any]]:
        """Run the full workflow and return results.

        Args:
            domains: Content domains (e.g., ["ai工具", "效率"]).
            count: Number of content pieces to generate.
            custom_topic: Optional specific topic to write about.
            account_tone: Persona tone for this account.
            account_vertical: Content vertical for this account.
            account_id: Matrix account identifier.
            competitor_context: Benchmark data text to inform topic selection.

        Returns:
            List of pipeline result dicts.
        """
        domains = domains or ["ai"]
        results = []

        for i in range(count):
            logger.info(
                "Generating content %d/%d (account=%s, vertical=%s)",
                i + 1,
                count,
                account_id or "default",
                account_vertical,
            )

            context = {
                "platform": self.platform,
                "domains": domains,
                "content_index": i,
                "custom_topic": custom_topic,
                "account_tone": account_tone,
                "account_vertical": account_vertical,
                "account_id": account_id,
                "competitor_context": competitor_context,
            }

            pipeline = self.build_pipeline()
            result = pipeline.run(context)

            # Push to Feishu if available
            if self.feishu and result.get("pipeline_success"):
                self._push_to_feishu(result)

            results.append(result)

        return results

    def _push_to_feishu(self, result: dict[str, Any]) -> None:
        """Push the final content to Feishu for review."""
        final: ContentFinal | None = result.get("final_content")
        if not final or not self.feishu:
            return

        try:
            doc_url = self.feishu.create_content_doc(final)
            final.feishu_doc_url = doc_url
            logger.info("Content pushed to Feishu: %s", doc_url)
        except Exception as e:
            logger.error("Failed to push to Feishu: %s", e)
