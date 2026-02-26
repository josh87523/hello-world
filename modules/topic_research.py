"""Topic research and selection module - enhanced with vertical-aware discovery."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ai.client import AIClient
from config.prompts.topic_research import format_refinement_prompt, format_trending_prompt
from core.pipeline import PipelineStep
from models.content import ContentIdea, Platform

logger = logging.getLogger(__name__)


class TopicResearchStep(PipelineStep):
    """Pipeline step that researches and selects a topic.

    Enhanced with:
    - Vertical-aware topic discovery (ai_tools, ai_tutorial, etc.)
    - Account persona tone injection
    - Save potential scoring
    - Emotional payoff type tagging

    Input context:
        - platform: Platform enum
        - domains: list[str]
        - custom_topic: optional str
        - account_tone: optional str (persona tone)
        - account_vertical: optional str (content vertical)

    Output context (added):
        - idea: ContentIdea
        - all_ideas: list[ContentIdea]
        - topic_outline: dict
    """

    def __init__(self, ai: AIClient):
        self.ai = ai

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        platform: Platform = context["platform"]
        domains: list[str] = context["domains"]
        custom_topic: str | None = context.get("custom_topic")
        tone: str = context.get("account_tone", "友好专业")
        vertical: str = context.get("account_vertical", "通用")

        if custom_topic:
            idea = ContentIdea(
                topic=custom_topic,
                angle="用户指定话题",
                keywords=domains,
                target_platforms=[platform],
                source="user_input",
            )
            ideas = [idea]
        else:
            ideas = self._discover_topics(platform, domains, tone, vertical)
            idea = self._select_best(ideas)

        outline = self._refine_topic(idea, platform, tone)

        context["idea"] = idea
        context["all_ideas"] = ideas
        context["topic_outline"] = outline
        return context

    def _discover_topics(
        self,
        platform: Platform,
        domains: list[str],
        tone: str = "友好专业",
        vertical: str = "通用",
        count: int = 5,
    ) -> list[ContentIdea]:
        """Use AI to discover trending topics with viral formula awareness."""
        prompt = format_trending_prompt(
            platform=platform.value,
            domains=domains,
            date=datetime.now().strftime("%Y-%m-%d"),
            count=count,
            tone=tone,
            vertical=vertical,
        )

        data = self.ai.chat_json(
            prompt,
            system="你是一位专业的小红书爆款选题策划师。请始终返回有效的JSON。",
        )
        topics = data.get("topics", []) if isinstance(data, dict) else data

        ideas = []
        for t in topics:
            idea = ContentIdea(
                topic=t.get("topic", ""),
                angle=t.get("angle", ""),
                keywords=t.get("keywords", []),
                trending_score=float(t.get("trending_score", 0)),
                competition_score=float(t.get("competition_score", 0)),
                target_platforms=[platform],
                source="ai_discovery",
                metadata={
                    "hook": t.get("hook", ""),
                    "reason": t.get("reason", ""),
                    "emotional_payoff": t.get("emotional_payoff", ""),
                    "save_potential": float(t.get("save_potential", 0)),
                },
            )
            ideas.append(idea)
            logger.info(
                "Topic: %s (trending=%.2f, competition=%.2f, save=%.2f)",
                idea.topic,
                idea.trending_score,
                idea.competition_score,
                idea.metadata.get("save_potential", 0),
            )

        return ideas

    def _select_best(self, ideas: list[ContentIdea]) -> ContentIdea:
        """Select the best topic based on composite scoring.

        Enhanced formula: save_potential contributes 30% of the score,
        because save/like ratio is the strongest viral predictor.

        Score = trending * 0.3 + (1 - competition) * 0.2 + save_potential * 0.5
        """
        if not ideas:
            raise ValueError("No topic ideas generated")

        def score(idea: ContentIdea) -> float:
            save_potential = idea.metadata.get("save_potential", 0.5)
            return (
                idea.trending_score * 0.3
                + (1 - idea.competition_score) * 0.2
                + save_potential * 0.5
            )

        best = max(ideas, key=score)
        logger.info("Selected topic: %s (score=%.3f)", best.topic, score(best))
        return best

    def _refine_topic(
        self, idea: ContentIdea, platform: Platform, tone: str = "友好专业"
    ) -> dict[str, Any]:
        """Refine the selected topic with detailed outline and save triggers."""
        prompt = format_refinement_prompt(
            topic=idea.topic,
            angle=idea.angle,
            platform=platform.value,
            tone=tone,
        )

        data = self.ai.chat_json(
            prompt,
            system="你是一位小红书选题优化师。请始终返回有效的JSON。",
        )
        return data if isinstance(data, dict) else {"outline": data}
