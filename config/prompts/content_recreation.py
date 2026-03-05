"""二创 prompt 模板 - 基于爆款原文改写，融合病毒公式。"""

from config.prompts.viral_formulas import (
    ANTI_AI_PHRASES,
    CONTENT_STRUCTURE_FORMULA,
    SAVE_OPTIMIZATION,
)

RECREATION_SYSTEM_PROMPT = (
    "你是一位小红书爆款内容二创专家，人设是「{tone}」。"
    "你擅长分析爆款笔记的底层逻辑，保留爆款骨架但完全重写为原创内容。"
    "你写的内容必须像真人写的，绝对不能有AI感。请始终返回有效的JSON。"
)

RECREATION_PROMPT = """\
## 任务
基于以下已验证的爆款笔记，进行深度二创改写。

## 原始爆款笔记
- 标题：{source_title}
- 正文：
{source_body}
- 标签：{source_tags}
- 数据：赞{likes} 藏{saves} 评{comments} 藏赞比{save_like_ratio}

## 二创原则（必须遵守）
1. **保留爆款骨架**：分析原文为什么火，保留核心结构和情绪节奏
2. **完全重写文字**：不能有任何一句话与原文相同，查重率 < 25%
3. **升级信息增量**：在原文基础上增加新观点、新案例、新数据
4. **强化收藏价值**：原文藏赞比={save_like_ratio}，二创要更高
5. **注入个人体感**：加入第一人称体验，制造真人感
{guidance_section}
{content_structure_formula}

{save_optimization}

{anti_ai_phrases}

## 小红书硬性规范
1. 标题：15-20字，含emoji，制造好奇/痛点/价值感，必须含数字和情绪词
2. 正文：开头3行=全部命运，每段emoji开头，关键词**加粗**，800-1500字
3. 标签：5-10个
4. 语气：像朋友在分享，不是老师在教学

## 输出格式（JSON）
{{
    "title": "二创标题（与原标题完全不同，但保留爆点元素）",
    "body": "二创正文（完全重写，保留结构骨架，含emoji和格式）",
    "tags": ["#标签1", "#标签2", ...],
    "cover_image_prompt": "封面图AI生成提示词（英文）",
    "image_prompts": ["配图提示词"],
    "save_hook": "收藏引导语",
    "recreation_analysis": "简述：原文为什么火 + 二创策略"
}}
"""


def format_recreation_prompt(
    source_title: str,
    source_body: str,
    source_tags: list[str],
    source_stats: dict,
    tone: str = "友好专业",
    domains: str = "",
    guidance: str = "",
) -> str:
    """格式化二创 prompt。"""
    guidance_section = ""
    if guidance:
        guidance_section = f"\n## 人工改写指导（优先级最高，必须遵循）\n{guidance}\n"

    save_like_ratio = source_stats.get("save_like_ratio", 0)
    if isinstance(save_like_ratio, (int, float)):
        save_like_ratio = f"{save_like_ratio:.2f}"

    return RECREATION_PROMPT.format(
        source_title=source_title,
        source_body=source_body[:3000],
        source_tags="、".join(source_tags[:10]),
        likes=source_stats.get("likes", 0),
        saves=source_stats.get("saves", 0),
        comments=source_stats.get("comments", 0),
        save_like_ratio=save_like_ratio,
        tone=tone,
        guidance_section=guidance_section,
        content_structure_formula=CONTENT_STRUCTURE_FORMULA,
        save_optimization=SAVE_OPTIMIZATION,
        anti_ai_phrases=ANTI_AI_PHRASES,
    )
