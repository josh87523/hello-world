"""Prompt templates for content optimization and quality checking.

Enhanced with research-backed scoring dimensions:
- save_potential: will users save this? (highest algorithm weight)
- originality: XHS score must be > 80 for promotion
- anti_ai: must pass human-written test
"""

from config.prompts.viral_formulas import ANTI_AI_PHRASES, XHS_ALGORITHM_RULES

CONTENT_OPTIMIZATION_PROMPT = """\
你是一位小红书内容优化专家，你的唯一目标是最大化这篇内容的收藏/赞比。

## 原始内容
标题：{title}
正文：{body}
标签：{tags}

{anti_ai_phrases}

## 优化维度（按优先级排序）
1. **收藏优化**：这篇内容有没有让人"想收藏备用"的冲动？
   - 是否有清单/步骤/模板等可收藏元素？
   - 有没有植入自然的收藏引导？
2. **开头3行**：展开前只显示3行，这3行能不能留住人？
   - 有没有钩子？数据？悬念？
3. **去AI感**：逐句检查，删除所有AI味表达
   - "首先""其次""值得注意"→全部替换为口语
   - 加入"亲测""说实话""踩过坑"等人设词
4. **标题优化**：是否符合0.3秒法则？有数字+情绪词？
5. **互动结尾**：结尾有没有有效的评论引导？
6. **标签精准度**：标签是否命中目标用户搜索词？

## 输出
返回优化后的完整内容，JSON格式：
{{
    "title": "优化后的标题",
    "body": "优化后的正文（确保已去除所有AI感表达）",
    "tags": ["优化后的标签"],
    "changes": ["修改说明1", "修改说明2", ...]
}}
"""

QUALITY_CHECK_PROMPT = """\
你是一位严格的小红书内容质量审核员。你的标准基于真实数据验证的爆款规律。

## 待审内容
平台：{platform}
标题：{title}
正文：{body}
标签：{tags}

{xhs_algorithm_rules}

## 评分维度（每项0-1分）

1. **hook_score**: 标题+前3行的吸引力
   - 0.9+: 看到就想点开，无法忽视
   - 0.7-0.9: 有吸引力但可以更好
   - <0.7: 会被划过

2. **save_potential**: 收藏价值（最重要的维度）
   - 0.9+: 有明确的清单/模板/教程，必收藏
   - 0.7-0.9: 有价值但不够"收藏级"
   - <0.7: 看完就走，不会收藏

3. **authenticity_score**: 真实感和人设一致性
   - 0.9+: 完全像真人写的，有个人体验
   - 0.7-0.9: 基本像人写的，偶有AI感
   - <0.7: 一眼AI，读者会划走

4. **engagement_score**: 互动潜力（会不会引发评论）
   - 0.9+: 有争议点或开放问题，必有人评论
   - 0.7-0.9: 有互动引导但力度不够
   - <0.7: 读完无感，没有评论冲动

5. **value_score**: 信息增量（读者能学到什么新东西）
   - 0.9+: 独家信息或深度洞察
   - 0.7-0.9: 有料但不够独特
   - <0.7: 老生常谈

6. **platform_fit_score**: 小红书平台适配度
   - 格式、排版、emoji使用、标签精准度、字数

## 合格标准
- overall_score >= 0.75 为通过（比之前0.7更严格）
- 任何单项 < 0.6 直接不通过
- authenticity_score < 0.7 直接不通过（去AI感是底线）

## 输出
以JSON格式返回：
{{
    "scores": {{
        "hook_score": 0.0,
        "save_potential": 0.0,
        "authenticity_score": 0.0,
        "engagement_score": 0.0,
        "value_score": 0.0,
        "platform_fit_score": 0.0
    }},
    "overall_score": 0.0,
    "feedback": "综合评价和具体改进建议",
    "failed_dimensions": ["列出不达标的维度"],
    "pass": true
}}
"""


def format_optimization_prompt(title: str, body: str, tags: str) -> str:
    """Format the optimization prompt with anti-AI rules."""
    return CONTENT_OPTIMIZATION_PROMPT.format(
        title=title,
        body=body,
        tags=tags,
        anti_ai_phrases=ANTI_AI_PHRASES,
    )


def format_quality_check_prompt(
    platform: str, title: str, body: str, tags: str
) -> str:
    """Format the quality check prompt with XHS algorithm rules."""
    return QUALITY_CHECK_PROMPT.format(
        platform=platform,
        title=title,
        body=body,
        tags=tags,
        xhs_algorithm_rules=XHS_ALGORITHM_RULES,
    )
