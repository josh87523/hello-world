"""Prompt templates for topic research - enhanced with viral content formulas."""

from config.prompts.viral_formulas import (
    EMOTIONAL_PAYOFF_TYPES,
    SAVE_OPTIMIZATION,
    TITLE_FORMULAS,
    VERTICAL_STRATEGIES,
)

TRENDING_TOPICS_PROMPT = """\
你是一位资深的小红书爆款选题策划师，擅长在{domains}领域发现高收藏率选题。

当前平台：{platform}
目标领域：{domains}
当前日期：{date}
账号人设语气：{tone}
内容垂类：{vertical}

{emotional_payoff_types}

{save_optimization}

## 选题原则（基于数据验证的爆款规律）
- 要有信息增量，不能是老生常谈
- 要能引发"收藏冲动"（清单型 > 教程型 > 模板型 > 对比型）
- 标题必须在0.3秒内抓住注意力
- 优先选择收藏/赞比 > 1.0 的内容类型
- 每个选题必须有一个明确的"情感满足类型"

请生成 {count} 个高潜力选题，每个选题包含：

1. topic: 选题标题（直击痛点，引发好奇）
2. angle: 独特切入角度（差异化视角）
3. keywords: 3-5个关键词
4. hook: 一句话钩子（前3行展示用，让人展开阅读）
5. trending_score: 热度评分 0-1
6. competition_score: 竞争度评分 0-1（0=蓝海，1=红海）
7. emotional_payoff: 主要情感满足类型（认同感/优越感/安全感/期待感/归属感）
8. save_potential: 收藏潜力 0-1（清单型最高，观点型最低）
9. reason: 为什么这个选题能火

请以 JSON 格式返回：
{{"topics": [{{...}}, ...]}}
"""

TOPIC_REFINEMENT_PROMPT = """\
你是一位小红书选题优化师，专注于最大化收藏/赞比。

原始选题：{topic}
切入角度：{angle}
目标平台：{platform}
账号人设：{tone}

{title_formulas}

请优化这个选题：
1. 生成 3 个标题变体（必须符合0.3秒法则：15-20字 + 数字 + 情绪词）
2. 细化内容大纲（3-5个核心要点，每个要点是一个独立价值点）
3. 建议的内容结构（钩子→价值→体感→互动）
4. 预期受众画像
5. 预期收藏触发点（用户为什么会收藏这篇）

以 JSON 格式返回：
{{"titles": [...], "outline": [...], "structure": "...", "audience": "...", "save_trigger": "..."}}
"""


def format_trending_prompt(
    platform: str,
    domains: list[str],
    date: str,
    count: int = 5,
    tone: str = "友好专业",
    vertical: str = "通用",
) -> str:
    """Format the trending topics prompt with all research-backed components."""
    return TRENDING_TOPICS_PROMPT.format(
        platform=platform,
        domains="、".join(domains),
        date=date,
        count=count,
        tone=tone,
        vertical=vertical,
        emotional_payoff_types=EMOTIONAL_PAYOFF_TYPES,
        save_optimization=SAVE_OPTIMIZATION,
    )


def format_refinement_prompt(
    topic: str,
    angle: str,
    platform: str,
    tone: str = "友好专业",
) -> str:
    """Format the topic refinement prompt with title formulas."""
    return TOPIC_REFINEMENT_PROMPT.format(
        topic=topic,
        angle=angle,
        platform=platform,
        tone=tone,
        title_formulas=TITLE_FORMULAS,
    )
