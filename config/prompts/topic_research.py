"""Prompt templates for topic research."""

TRENDING_TOPICS_PROMPT = """\
你是一位资深的自媒体选题策划师，擅长在{domains}领域发现爆款选题。

当前平台：{platform}
目标领域：{domains}
当前日期：{date}

请为我生成 {count} 个高潜力选题，每个选题需要包含：

1. topic: 选题标题（直击痛点，引发好奇）
2. angle: 独特的切入角度（差异化视角）
3. keywords: 3-5个关键词
4. hook: 一句话钩子（让人忍不住点进来看）
5. trending_score: 热度评分 0-1（基于你对当前趋势的判断）
6. competition_score: 竞争度评分 0-1（0=蓝海，1=红海）
7. reason: 为什么这个选题能火

选题原则：
- 要有信息增量，不能是老生常谈
- 要能引发共鸣或争议
- 标题要有画面感和冲击力
- 优先选择能提供实操价值的选题
- 结合当前热点和长青话题

请以 JSON 格式返回，格式为：
{{"topics": [{{...}}, ...]}}
"""

TOPIC_REFINEMENT_PROMPT = """\
你是一位自媒体选题优化师。

原始选题：{topic}
切入角度：{angle}
目标平台：{platform}

请优化这个选题：
1. 生成 3 个更吸引人的标题变体
2. 细化内容大纲（3-5 个核心要点）
3. 建议的内容结构
4. 预期受众画像

以 JSON 格式返回：
{{"titles": [...], "outline": [...], "structure": "...", "audience": "..."}}
"""
