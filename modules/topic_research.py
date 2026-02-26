"""Topic research and selection module."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ai.client import AIClient
from config.prompts.topic_research import TRENDING_TOPICS_PROMPT, TOPIC_REFINEMENT_PROMPT
from core.pipeline import PipelineStep
from models.content import ContentIdea, Platform

logger = logging.getLogger(__name__)


class TopicResearchStep(PipelineStep):
    """Pipeline step that researches and selects a topic.

    Input context:
        - platform: Platform enum
        - domains: list[str]
        - custom_topic: optional str

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
            ideas = self._discover_topics(platform, domains)
            idea = self._select_best(ideas)

        # Refine the selected topic
        outline = self._refine_topic(idea, platform)

        context["idea"] = idea
        context["all_ideas"] = ideas
        context["topic_outline"] = outline
        return context

    def _discover_topics(
        self, platform: Platform, domains: list[str], count: int = 5
    ) -> list[ContentIdea]:
        """Use AI to discover trending topics."""
        prompt = TRENDING_TOPICS_PROMPT.format(
            platform=platform.value,
            domains="、".join(domains),
            date=datetime.now().strftime("%Y-%m-%d"),
            count=count,
        )

        data = self.ai.chat_json(prompt, system="你是一位专业的自媒体选题策划师。请始终返回有效的JSON。")
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
                metadata={"hook": t.get("hook", ""), "reason": t.get("reason", "")},
            )
            ideas.append(idea)
            logger.info(
                "Topic found: %s (trending=%.2f, competition=%.2f)",
                idea.topic,
                idea.trending_score,
                idea.competition_score,
            )

        return ideas

    def _select_best(self, ideas: list[ContentIdea]) -> ContentIdea:
        """Select the best topic based on scoring.

        Score = trending_score * 0.6 + (1 - competition_score) * 0.4
        Higher trending + lower competition = better.
        """
        if not ideas:
            raise ValueError("No topic ideas generated")

        def score(idea: ContentIdea) -> float:
            return idea.trending_score * 0.6 + (1 - idea.competition_score) * 0.4

        best = max(ideas, key=score)
        logger.info("Selected topic: %s (score=%.3f)", best.topic, score(best))
        return best

    def _refine_topic(self, idea: ContentIdea, platform: Platform) -> dict[str, Any]:
        """Refine the selected topic with detailed outline."""
        prompt = TOPIC_REFINEMENT_PROMPT.format(
            topic=idea.topic,
            angle=idea.angle,
            platform=platform.value,
        )

        data = self.ai.chat_json(prompt, system="你是一位自媒体选题优化师。请始终返回有效的JSON。")
        return data if isinstance(data, dict) else {"outline": data}
