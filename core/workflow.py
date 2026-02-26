"""Main content workflow orchestrator."""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from core.pipeline import Pipeline
from models.content import ContentFinal, Platform

logger = logging.getLogger(__name__)


class ContentWorkflow:
    """Orchestrates the full content creation workflow.

    This is the main entry point that builds and runs the pipeline
    for a given platform and content domain.

    Usage:
        workflow = ContentWorkflow(ai_client=client, platform=Platform.XIAOHONGSHU)
        results = workflow.run(domains=["ai", "创业", "写作"], count=3)
    """

    def __init__(
        self,
        ai_client: AIClient,
        platform: Platform = Platform.XIAOHONGSHU,
        feishu_client: Any | None = None,
    ):
        self.ai = ai_client
        self.platform = platform
        self.feishu = feishu_client

    def build_pipeline(self) -> Pipeline:
        """Build the full content pipeline with all steps."""
        from modules.topic_research import TopicResearchStep
        from modules.content_generator import ContentGenerationStep
        from modules.content_optimizer import ContentOptimizationStep
        from modules.quality_checker import QualityCheckStep

        pipeline = Pipeline(name=f"content-{self.platform.value}")
        pipeline.add_step(TopicResearchStep(self.ai))
        pipeline.add_step(ContentGenerationStep(self.ai))
        pipeline.add_step(ContentOptimizationStep(self.ai))
        pipeline.add_step(QualityCheckStep(self.ai))

        return pipeline

    def run(
        self,
        domains: list[str] | None = None,
        count: int = 1,
        custom_topic: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run the full workflow and return results.

        Args:
            domains: Content domains (e.g., ["ai", "创业", "写作"]).
            count: Number of content pieces to generate.
            custom_topic: Optional specific topic to write about.

        Returns:
            List of pipeline result dicts.
        """
        domains = domains or ["ai"]
        results = []

        for i in range(count):
            logger.info("Generating content %d/%d", i + 1, count)

            context = {
                "platform": self.platform,
                "domains": domains,
                "content_index": i,
                "custom_topic": custom_topic,
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
