"""Composable pipeline engine for content workflow steps."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class PipelineStep(ABC):
    """Base class for all pipeline steps.

    Each step takes an input context dict and returns an updated context dict.
    Steps are composable and can be added/removed from the pipeline.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute this pipeline step.

        Args:
            context: Shared context dict passed between steps.

        Returns:
            Updated context dict.
        """
        ...

    def validate(self, context: dict[str, Any]) -> bool:
        """Validate preconditions before execution. Override to add checks."""
        return True


@dataclass
class Pipeline:
    """A sequence of PipelineSteps executed in order.

    The pipeline passes a shared context dict through each step.
    If any step fails, the pipeline stops and returns the error in context.

    Usage:
        pipeline = Pipeline(steps=[
            TopicResearchStep(ai_client),
            ContentGenerationStep(ai_client),
            ContentOptimizationStep(ai_client),
            QualityCheckStep(ai_client),
        ])
        result = pipeline.run({"platform": "xiaohongshu", "domain": "ai"})
    """

    steps: list[PipelineStep] = field(default_factory=list)
    name: str = "default"

    def add_step(self, step: PipelineStep) -> Pipeline:
        self.steps.append(step)
        return self

    def run(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run all steps in sequence."""
        ctx = context or {}
        ctx.setdefault("errors", [])
        ctx.setdefault("completed_steps", [])

        logger.info("Pipeline [%s] starting with %d steps", self.name, len(self.steps))

        for step in self.steps:
            step_name = step.name
            logger.info("Running step: %s", step_name)

            if not step.validate(ctx):
                msg = f"Validation failed for step: {step_name}"
                logger.error(msg)
                ctx["errors"].append({"step": step_name, "error": msg})
                break

            try:
                ctx = step.execute(ctx)
                ctx["completed_steps"].append(step_name)
                logger.info("Step completed: %s", step_name)
            except Exception as e:
                msg = f"Step {step_name} failed: {e}"
                logger.error(msg, exc_info=True)
                ctx["errors"].append({"step": step_name, "error": str(e)})
                break

        success = len(ctx["errors"]) == 0
        ctx["pipeline_success"] = success
        logger.info(
            "Pipeline [%s] %s. Steps completed: %d/%d",
            self.name,
            "succeeded" if success else "failed",
            len(ctx["completed_steps"]),
            len(self.steps),
        )
        return ctx
