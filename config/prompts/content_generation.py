"""Prompt templates for content generation - enhanced with viral formulas."""

from config.prompts.viral_formulas import (
    ANTI_AI_PHRASES,
    CONTENT_STRUCTURE_FORMULA,
    SAVE_OPTIMIZATION,
    TITLE_FORMULAS,
)

XIAOHONGSHU_CONTENT_PROMPT = """\
你是一位小红书爆款内容创作者，精通{domains}领域。
你的人设语气是：{tone}

## 任务
根据以下选题信息，创作一篇小红书图文内容。目标是最大化收藏/赞比。

## 选题信息
- 标题：{title}
- 角度：{angle}
- 关键词：{keywords}
- 内容大纲：{outline}
- 收藏触发点：{save_trigger}

{content_structure_formula}

{save_optimization}

{anti_ai_phrases}

## 小红书硬性规范
1. **标题**：15-20字，含emoji，制造好奇/痛点/价值感，必须含数字和情绪词
2. **正文**：
   - 开头3行=全部命运（展开前只显示3行）
   - 每段用emoji开头做视觉分隔
   - 关键词**加粗**
   - 必须有第一人称体验和踩坑经历
   - 结尾必须有互动引导
3. **字数**：800-1500字
4. **标签**：5-10个相关话题标签
5. **语气**：像朋友在分享，不是老师在教学

## 输出格式
请以 JSON 格式返回：
{{
    "title": "最终标题（符合0.3秒法则）",
    "body": "正文内容（含emoji和格式，去除所有AI感）",
    "tags": ["#标签1", "#标签2", ...],
    "cover_image_prompt": "封面图AI生成提示词（英文，高对比色，大字）",
    "image_prompts": ["配图1提示词", "配图2提示词", ...],
    "save_hook": "文中的收藏引导语"
}}
"""

GENERIC_CONTENT_PROMPT = """\
你是一位专业的自媒体内容创作者，精通{domains}领域。

## 任务
根据选题创作适合 {platform} 平台的内容。

## 选题信息
- 标题：{title}
- 角度：{angle}
- 关键词：{keywords}

{content_structure_formula}

## 要求
- 符合平台调性和内容规范
- 有价值、有深度、有互动性
- 适当使用格式增强可读性
- 去除AI味词汇，保持人设感

请以 JSON 格式返回：
{{
    "title": "最终标题",
    "body": "正文内容",
    "tags": ["标签1", "标签2", ...],
    "cover_image_prompt": "封面图AI生成提示词（英文）"
}}
"""


def format_xhs_content_prompt(
    title: str,
    angle: str,
    keywords: str,
    outline: str,
    domains: str,
    tone: str = "友好专业",
    save_trigger: str = "",
) -> str:
    """Format the XHS content prompt with all viral formula components."""
    return XIAOHONGSHU_CONTENT_PROMPT.format(
        title=title,
        angle=angle,
        keywords=keywords,
        outline=outline,
        domains=domains,
        tone=tone,
        save_trigger=save_trigger or "提供实用价值让用户想收藏备用",
        content_structure_formula=CONTENT_STRUCTURE_FORMULA,
        save_optimization=SAVE_OPTIMIZATION,
        anti_ai_phrases=ANTI_AI_PHRASES,
    )


def format_generic_content_prompt(
    title: str,
    angle: str,
    keywords: str,
    platform: str,
    domains: str,
) -> str:
    """Format the generic content prompt."""
    return GENERIC_CONTENT_PROMPT.format(
        title=title,
        angle=angle,
        keywords=keywords,
        platform=platform,
        domains=domains,
        content_structure_formula=CONTENT_STRUCTURE_FORMULA,
    )
