"""Mock AI client for testing the full pipeline without API calls."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Pre-built mock responses keyed by prompt pattern
_MOCK_TOPICS = {
    "topics": [
        {
            "topic": "AI Agent 正在悄悄替代初级程序员，你准备好了吗？",
            "angle": "从真实招聘数据切入，揭示AI对初级岗位的冲击",
            "keywords": ["AI Agent", "程序员", "失业", "转型", "效率"],
            "hook": "上周我朋友被裁了，不是因为能力不行，是因为 AI 能干他的活了",
            "trending_score": 0.9,
            "competition_score": 0.4,
            "reason": "AI替代论是长青话题，但用真实数据+亲身经历切入有差异化",
        },
        {
            "topic": "我用 AI 写了30天小红书，涨粉5000的真实复盘",
            "angle": "用第一人称复盘，分享具体方法论和踩坑经验",
            "keywords": ["AI写作", "小红书", "涨粉", "自媒体", "复盘"],
            "hook": "别再手动想选题了，我用一套AI工作流实现了日更",
            "trending_score": 0.85,
            "competition_score": 0.5,
            "reason": "实操复盘类内容收藏率极高，AI+自媒体是热门赛道",
        },
        {
            "topic": "创业者必备的5个 AI 工具，帮你省掉一个全职员工",
            "angle": "从创业者降本增效的痛点出发，推荐实用工具链",
            "keywords": ["创业", "AI工具", "降本增效", "效率", "工具推荐"],
            "hook": "创业第一年，我靠这5个AI工具省了20万人力成本",
            "trending_score": 0.8,
            "competition_score": 0.6,
            "reason": "工具推荐类内容实用性强，创业者群体付费意愿高",
        },
    ]
}

_MOCK_REFINEMENT = {
    "titles": [
        "AI Agent 正在悄悄替代初级程序员，你准备好了吗？",
        "2026年了，初级程序员还有未来吗？",
        "AI 一天干完你一周的活，程序员该慌了吗？",
    ],
    "outline": [
        "现象：大厂缩减初级岗位招聘，AI编程工具使用率激增",
        "数据：哪些岗位正在被AI替代，哪些反而更吃香",
        "案例：我身边3个程序员朋友的不同选择和结局",
        "方法：普通程序员如何借AI转型，而不是被AI干掉",
        "行动：今天就能开始的3件事",
    ],
    "structure": "钩子开头 → 现象描述 → 数据佐证 → 真实案例 → 解决方案 → 行动号召",
    "audience": "25-35岁互联网从业者，尤其是初中级程序员和想转型的技术人",
}

_MOCK_CONTENT = {
    "title": "💻 AI 一天干完你一周的活，程序员该慌吗？",
    "body": (
        "上周，我一个在大厂做前端的朋友被裁了。\n\n"
        "不是因为他能力不行，而是他的leader发现——\n"
        "用 Cursor + Claude，一个高级工程师能顶3个初级的活。\n\n"
        "🔥 这不是段子，这是正在发生的事\n\n"
        "我翻了一下最近的招聘数据：\n"
        "• 某大厂2026年校招名额比去年砍了40%\n"
        "• 但「AI应用工程师」岗位增长了200%\n"
        "• 会用AI工具的程序员，薪资溢价15-30%\n\n"
        "📊 哪些岗位危险了？\n\n"
        "高危：简单CRUD、页面切图、基础测试\n"
        "安全：架构设计、需求分析、复杂业务逻辑\n"
        "新机会：AI应用开发、Prompt Engineering、AI Infra\n\n"
        "💡 我身边3个朋友的真实故事\n\n"
        "朋友A：坚持不碰AI，觉得是炒作 → 被裁\n"
        "朋友B：用AI提效，产出翻倍 → 升职\n"
        "朋友C：转型AI应用开发 → 涨薪50%\n\n"
        "同样的背景，不同的选择，差距已经拉开了。\n\n"
        "✅ 今天就能开始的3件事\n\n"
        "1. 把 Cursor/Copilot 用起来，先让AI帮你写30%的代码\n"
        "2. 每周花2小时学一个AI工具（推荐从Claude开始）\n"
        "3. 开始做AI相关的side project，简历上最好的加分项\n\n"
        "记住：AI不会替代程序员，但会用AI的程序员会替代不会的。\n\n"
        "你觉得AI会替代你的工作吗？评论区聊聊 👇"
    ),
    "tags": ["#AI", "#程序员", "#人工智能", "#转型", "#职场", "#效率", "#Claude", "#Cursor"],
    "cover_image_prompt": "A futuristic split-screen illustration: left side shows a stressed programmer at a desk with old computer, right side shows a confident programmer collaborating with AI holographic interface, modern minimalist style, blue and orange color scheme",
    "image_prompts": [
        "Infographic showing job market trends: AI jobs growing vs traditional coding jobs declining, clean data visualization style",
        "Three cartoon characters representing different career paths: one falling, one rising, one transforming, simple flat illustration",
    ],
}

_MOCK_OPTIMIZATION = {
    "title": "💻 AI一天干完你一周的活，程序员真该慌了",
    "body": (
        "上周，我一个大厂前端朋友被裁了。\n\n"
        "不是能力不行。\n"
        "是他leader发现，Cursor + Claude 让一个高级工程师顶3个初级。\n\n"
        "🔥 这不是段子，是正在发生的事\n\n"
        "看一组数据：\n"
        "• 某大厂2026校招名额砍了40%\n"
        "• 「AI应用工程师」岗位暴涨200%\n"
        "• 会AI工具的程序员，薪资多15-30%\n\n"
        "📊 哪些岗位危了？\n\n"
        "❌ 高危：CRUD、切图、基础测试\n"
        "✅ 安全：架构设计、需求分析、复杂业务\n"
        "🚀 新机会：AI应用开发、Prompt Engineering\n\n"
        "💡 3个朋友，3种结局\n\n"
        "A：死活不碰AI → 被裁\n"
        "B：用AI提效，产出翻倍 → 升职\n"
        "C：转AI应用开发 → 涨薪50%\n\n"
        "同样的起点，差距已经拉开了。\n\n"
        "✅ 今天就能做的3件事\n\n"
        "1. 装上 Cursor，先让AI帮你写30%代码\n"
        "2. 每周2小时学一个AI工具（先从Claude开始）\n"
        "3. 搞一个AI side project，这是简历最强加分项\n\n"
        "AI不会替代程序员。\n但会用AI的程序员，会替代不会的。\n\n"
        "你觉得AI会替代你吗？评论区聊 👇"
    ),
    "tags": ["#AI", "#程序员", "#人工智能", "#转型", "#职场", "#效率提升", "#Claude", "#求职"],
    "changes": [
        "标题缩短并加强紧迫感",
        "开头三行更紧凑，适配小红书折叠显示",
        "数据段落精简，去掉冗余表述",
        "案例部分用更短的句式增加冲击力",
        "结尾金句拆成两行增强记忆点",
        "去除'首先其次最后'等AI感连接词",
    ],
}

_MOCK_QUALITY = {
    "scores": {
        "hook_score": 0.9,
        "value_score": 0.85,
        "readability_score": 0.9,
        "engagement_score": 0.85,
        "authenticity_score": 0.8,
        "platform_fit_score": 0.9,
    },
    "overall_score": 0.87,
    "feedback": "内容质量优秀。标题有吸引力，开头三行能有效留住读者。数据和案例结合好，有说服力。结尾互动引导自然。建议：可以在评论区准备几条引导性回复，进一步提升互动率。",
    "pass": True,
}

_MOCK_RECREATION = {
    "title": "🤖 用AI写代码的程序员，正在悄悄甩开同事",
    "body": (
        "说个真事。\n\n"
        "我组里一个同事，上个月开始偷偷用Cursor写代码。\n"
        "结果呢？产出直接翻倍，leader都懵了。\n\n"
        "🔥 这不是个例，是趋势\n\n"
        "我问了身边十几个程序员朋友：\n"
        "• 8个已经在用AI写代码\n"
        "• 3个在观望\n"
        "• 只有1个坚决不用\n"
        "猜猜谁最近被优化了？\n\n"
        "📊 说几个扎心的数据\n\n"
        "用AI的程序员平均节省**40%编码时间**\n"
        "不用AI的，加班时长反而增加了20%\n"
        "差距不是在缩小，是在加速拉大\n\n"
        "💡 我自己的真实体验\n\n"
        "一开始我也抵触，觉得AI写的代码不靠谱。\n"
        "后来试了一周Cursor + Claude——\n"
        "emmm，真香。\n\n"
        "最明显的变化：以前写个CRUD要半天，现在20分钟搞定。\n"
        "省下的时间去做架构设计，反而涨了薪。\n\n"
        "✅ 三个建议给还在犹豫的你\n\n"
        "1. 先别想太多，装个Cursor用一周再说\n"
        "2. 从简单任务开始，写测试用例、写文档\n"
        "3. 慢慢过渡到核心业务代码\n\n"
        "说实话，AI不会替代程序员。\n"
        "但会用AI的那个人，会拿到你的offer。\n\n"
        "你们团队用AI了吗？评论区聊聊 👇\n\n"
        "先收藏再慢慢看，以后一定用得上 📌"
    ),
    "tags": ["#AI编程", "#程序员", "#Cursor", "#效率提升", "#职场", "#Claude", "#程序员日常", "#转型"],
    "cover_image_prompt": "Split illustration: left side frustrated programmer with messy desk, right side confident programmer with AI holographic assistant, modern flat design, purple and orange gradient",
    "image_prompts": ["Bar chart comparing productivity with and without AI coding tools"],
    "save_hook": "先收藏再慢慢看，以后一定用得上",
    "recreation_analysis": "原文用真实裁员案例制造焦虑+数据佐证+行动方案，二创保留结构但换成同事视角，更接地气",
}


class MockAIClient:
    """Mock AI client that returns pre-built responses for testing."""

    def __init__(self):
        self.call_count = 0
        self.model = "mock-claude"
        self._mode = "original"  # or "recreation"

    def set_mode(self, mode: str) -> None:
        """Set mock response mode: 'original' or 'recreation'."""
        self._mode = mode
        self.call_count = 0

    def chat(self, prompt: str, system: str = "", **kwargs) -> str:
        self.call_count += 1
        logger.info("[MockAI] chat call #%d (%d chars prompt)", self.call_count, len(prompt))
        return "Mock response"

    def chat_json(self, prompt: str, system: str = "", **kwargs) -> dict[str, Any] | list[Any]:
        self.call_count += 1

        if self._mode == "recreation":
            # Recreation pipeline: 1=recreation, 2=optimization, 3=cover, 4=quality
            responses = [_MOCK_RECREATION, _MOCK_OPTIMIZATION, _MOCK_CONTENT, _MOCK_QUALITY]
            labels = ["recreation", "optimization", "cover", "quality"]
        else:
            # Original pipeline: 1=topics, 2=refinement, 3=content, 4=optimization, 5=quality
            responses = [_MOCK_TOPICS, _MOCK_REFINEMENT, _MOCK_CONTENT, _MOCK_OPTIMIZATION, _MOCK_QUALITY]
            labels = ["topics", "refinement", "content", "optimization", "quality"]

        idx = (self.call_count - 1) % len(responses)
        logger.info("[MockAI] chat_json call #%d → %s", self.call_count, labels[idx])
        return responses[idx]

    def chat_messages(self, messages: list[dict[str, str]], **kwargs) -> str:
        return self.chat(messages[-1].get("content", ""), **kwargs)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
