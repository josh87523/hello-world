"""Cover image strategy and A/B variant generation.

Based on research findings:
- Cover determines 80% of click-through rate (CTR)
- Users decide in 0.3 seconds whether to stop scrolling
- Changing cover alone improved CTR from 8% to 23% in one case study
- Success threshold: click cost < 0.2 RMB AND completion rate > 40%

Source: 创富矩阵流量咨询 (2,776赞, 3,096收藏)
"""

from __future__ import annotations

import logging
from typing import Any

from ai.client import AIClient
from core.pipeline import PipelineStep

logger = logging.getLogger(__name__)


COVER_VARIANT_PROMPT = """\
你是一位小红书封面设计专家，精通视觉传达和用户心理。

## 内容信息
标题：{title}
正文摘要：{summary}
内容垂类：{vertical}
目标人设语气：{tone}

## 封面设计原则（0.3秒法则）
- 用户在0.3秒内决定是否停留
- 手机缩略图状态下也必须能看清核心信息
- 封面比例3:4（小红书标准）
- 高信息密度 + 高情绪冲击力 = 最佳象限

## 请生成 {count} 个不同风格的封面方案

每个方案包含：
1. style: 封面类型（文字冲击型/信息清单型/场景代入型/数据对比型/情绪共鸣型）
2. text_overlay: 封面上的文字（不超过10个字，要大到缩略图能看清）
3. color_scheme: 配色方案（使用高对比色：白底红字/黑底黄字/深蓝底白字）
4. layout: 布局描述（元素位置和大小）
5. image_prompt: AI图像生成的英文提示词（详细描述画面内容、风格、构图）
6. rationale: 为什么这个方案能吸引点击（一句话）

以JSON格式返回：
{{"cover_variants": [{{...}}, ...]}}
"""


class CoverStrategyStep(PipelineStep):
    """Pipeline step that generates multiple cover variants for A/B testing.

    Produces 3-5 cover variants with different visual strategies. The best
    performing cover can be identified through post-publishing A/B testing
    (赛马机制: 5 covers x 30 RMB each x 6 hours).

    Input context:
        - draft: ContentDraft (with title and body)
        - account_tone (optional): str
        - account_vertical (optional): str

    Output context (added):
        - cover_variants: list[dict] - cover options for A/B testing
        - recommended_cover: dict - the AI-recommended best option
    """

    def __init__(self, ai: AIClient, variant_count: int = 3):
        self.ai = ai
        self.variant_count = variant_count

    def validate(self, context: dict[str, Any]) -> bool:
        return "draft" in context

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        draft = context["draft"]
        tone = context.get("account_tone", "友好专业")
        vertical = context.get("account_vertical", "通用")

        prompt = COVER_VARIANT_PROMPT.format(
            count=self.variant_count,
            title=draft.title,
            summary=draft.body[:300],
            vertical=vertical,
            tone=tone,
        )

        data = self.ai.chat_json(
            prompt,
            system="你是一位小红书封面设计专家。请始终返回有效的JSON。",
            temperature=0.7,
        )

        variants = data.get("cover_variants", [])

        logger.info(
            "Generated %d cover variants for '%s'", len(variants), draft.title
        )

        # Use the first variant as the primary cover prompt
        if variants:
            draft.cover_image_prompt = variants[0].get(
                "image_prompt", draft.cover_image_prompt
            )
            # Store all variant image prompts for A/B testing
            draft.image_prompts = [
                v.get("image_prompt", "") for v in variants if v.get("image_prompt")
            ]

        context["cover_variants"] = variants
        context["recommended_cover"] = variants[0] if variants else {}
        context["draft"] = draft
        return context
