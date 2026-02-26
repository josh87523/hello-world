"""Competitor/benchmark account analysis engine.

Analyzes scraped competitor data to extract actionable patterns:
- Title formulas that drive high save/like ratios
- Content structure patterns from top-performing notes
- Tag strategies and posting frequency
- Style analysis for persona calibration

The output feeds directly into the topic research step to inform
content strategy.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime
from typing import Any

from ai.client import AIClient
from models.competitor import BenchmarkReport, CompetitorAccount, ScrapedNote
from modules.xhs_scraper import ScraperConfig, XhsScraper

logger = logging.getLogger(__name__)

BENCHMARK_DATA_FILE = "data/benchmark.json"

# ------------------------------------------------------------------
# Prompts for AI-powered analysis
# ------------------------------------------------------------------

TITLE_PATTERN_PROMPT = """\
你是一位小红书内容分析专家。

以下是一组高赞笔记的标题列表（按互动量从高到低排序）：

{titles}

请分析这些标题的共同规律，提炼出可复用的标题公式：

1. 识别出 5 个最常用的标题结构模式（如"数字+痛点+解决方案"）
2. 提取高频情绪词和钩子词
3. 分析标题长度分布
4. 总结什么类型的标题互动最高

以JSON格式返回：
{{
    "title_patterns": ["模式1: 描述+示例", "模式2: ..."],
    "power_words": ["高频情绪词1", "情绪词2", ...],
    "avg_title_length": 0,
    "top_insight": "最重要的一条发现"
}}
"""

CONTENT_STYLE_PROMPT = """\
你是一位自媒体内容策略分析师。

以下是某个高赞小红书博主的多篇笔记内容摘要：

账号名称：{nickname}
粉丝数：{followers}
垂类领域：{vertical}

--- 笔记内容 ---
{notes_text}
---

请分析该博主的内容风格和策略，输出以下维度：

1. **写作风格**：语气/人设/用词特点
2. **内容结构**：开头、正文、结尾的惯用套路
3. **高赞密码**：哪些笔记数据最好，为什么
4. **可复用策略**：我们可以直接借鉴的3个具体做法
5. **差异化建议**：如何在模仿的基础上做出差异

以JSON格式返回：
{{
    "writing_style": "...",
    "content_structure": "...",
    "viral_factors": ["因素1", "因素2", ...],
    "reusable_strategies": ["策略1", "策略2", "策略3"],
    "differentiation": "..."
}}
"""

BENCHMARK_SUMMARY_PROMPT = """\
你是一位自媒体矩阵运营专家。

以下是我们分析的多个对标账号的综合数据：

{competitor_summaries}

基于以上数据，请给出：

1. **行业基准线**：平均点赞/收藏/评论数、收藏赞比均值
2. **最值得对标的账号**及原因
3. **共同的高赞内容特征**
4. **选题策略建议**：基于对标数据，下一阶段应该重点做什么选题
5. **差距分析**：我们目前每周8篇×7天=56篇产出，要达到每周稳定过千互动爆款，
   按照对标账号的爆款率，需要做到什么水平

以JSON格式返回：
{{
    "benchmarks": {{
        "avg_likes": 0,
        "avg_saves": 0,
        "avg_save_like_ratio": 0,
        "viral_rate": 0
    }},
    "best_competitor": {{
        "nickname": "...",
        "reason": "..."
    }},
    "common_viral_traits": ["特征1", "特征2", ...],
    "topic_recommendations": ["建议1", "建议2", ...],
    "gap_analysis": "...",
    "action_items": ["行动1", "行动2", "行动3"]
}}
"""


class CompetitorAnalyzer:
    """Analyzes competitor accounts and generates benchmark reports.

    Usage:
        analyzer = CompetitorAnalyzer(ai_client, scraper)

        # Add competitors to track
        analyzer.add_competitor("user_id_1", "博主昵称", vertical="ai_tools")

        # Scrape and analyze
        report = analyzer.run_full_analysis()

        # Get insights for topic research
        insights = analyzer.get_topic_insights()
    """

    def __init__(
        self,
        ai: AIClient | None = None,
        scraper: XhsScraper | None = None,
        data_file: str = BENCHMARK_DATA_FILE,
    ):
        self.ai = ai
        self.scraper = scraper
        self.data_file = data_file
        self.competitors: list[CompetitorAccount] = []
        self.all_notes: dict[str, list[ScrapedNote]] = {}  # user_id -> notes
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.competitors = [
                CompetitorAccount.from_dict(c) for c in data.get("competitors", [])
            ]
            for user_id, notes_data in data.get("notes", {}).items():
                self.all_notes[user_id] = [
                    ScrapedNote.from_dict(n) for n in notes_data
                ]
            logger.info(
                "Loaded %d competitors, %d total notes",
                len(self.competitors),
                sum(len(v) for v in self.all_notes.values()),
            )

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.data_file) or ".", exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "competitors": [c.to_dict() for c in self.competitors],
            "notes": {
                uid: [n.to_dict() for n in notes]
                for uid, notes in self.all_notes.items()
            },
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Competitor management
    # ------------------------------------------------------------------

    def add_competitor(
        self,
        user_id: str,
        nickname: str,
        vertical: str = "",
        home_url: str = "",
    ) -> CompetitorAccount:
        """Add a competitor account to track."""
        # Check for duplicates
        for c in self.competitors:
            if c.user_id == user_id:
                logger.info("Competitor already exists: %s", nickname)
                return c

        competitor = CompetitorAccount(
            user_id=user_id,
            nickname=nickname,
            vertical=vertical,
            home_url=home_url,
        )
        self.competitors.append(competitor)
        self.save()
        logger.info("Added competitor: %s (%s)", nickname, user_id)
        return competitor

    def remove_competitor(self, user_id: str) -> bool:
        before = len(self.competitors)
        self.competitors = [c for c in self.competitors if c.user_id != user_id]
        self.all_notes.pop(user_id, None)
        if len(self.competitors) < before:
            self.save()
            return True
        return False

    def list_competitors(self) -> list[CompetitorAccount]:
        return self.competitors

    # ------------------------------------------------------------------
    # Scraping
    # ------------------------------------------------------------------

    def scrape_competitor(
        self, user_id: str, count: int = 30
    ) -> list[ScrapedNote]:
        """Scrape a competitor's notes and update stored data."""
        if not self.scraper:
            logger.error("Scraper not configured")
            return []

        notes = self.scraper.scrape_user_notes(user_id, count=count)
        if notes:
            self.all_notes[user_id] = notes
            # Update competitor metadata
            for c in self.competitors:
                if c.user_id == user_id:
                    c.total_notes = len(notes)
                    c.last_scraped = datetime.now().isoformat()
                    break
            self.save()

        return notes

    def scrape_all_competitors(self, count: int = 30) -> int:
        """Scrape all tracked competitors. Returns total notes scraped."""
        total = 0
        for comp in self.competitors:
            notes = self.scrape_competitor(comp.user_id, count)
            total += len(notes)
            logger.info("Scraped %s: %d notes", comp.nickname, len(notes))
        return total

    def scrape_keyword(
        self, keyword: str, count: int = 40
    ) -> list[ScrapedNote]:
        """Search and scrape notes by keyword for competitive research."""
        if not self.scraper:
            logger.error("Scraper not configured")
            return []

        return self.scraper.search_notes(keyword, count=count)

    # ------------------------------------------------------------------
    # Analysis (local, no AI needed)
    # ------------------------------------------------------------------

    def compute_competitor_stats(self, user_id: str) -> CompetitorAccount | None:
        """Compute stats for a single competitor from their notes."""
        comp = next((c for c in self.competitors if c.user_id == user_id), None)
        notes = self.all_notes.get(user_id, [])

        if not comp or not notes:
            return comp

        # Basic stats
        total_likes = sum(n.likes for n in notes)
        total_saves = sum(n.saves for n in notes)
        comp.avg_likes = total_likes / len(notes) if notes else 0
        comp.avg_saves = total_saves / len(notes) if notes else 0
        comp.avg_save_like_ratio = (
            total_saves / total_likes if total_likes > 0 else 0
        )
        comp.total_notes = len(notes)

        # Viral rate
        viral_count = sum(1 for n in notes if n.total_interactions >= 1000)
        comp.viral_rate = viral_count / len(notes) if notes else 0

        # Top notes
        sorted_notes = sorted(notes, key=lambda n: n.total_interactions, reverse=True)
        comp.top_note_ids = [n.note_id for n in sorted_notes[:10]]

        # Common tags
        all_tags = []
        for n in notes:
            all_tags.extend(n.tags)
        tag_counts = Counter(all_tags)
        comp.common_tags = [tag for tag, _ in tag_counts.most_common(20)]

        # Title patterns (will be enhanced by AI)
        comp.common_title_patterns = [n.title for n in sorted_notes[:5]]

        # Posting frequency estimate
        if len(notes) >= 2:
            try:
                dates = sorted(
                    [
                        datetime.fromisoformat(n.scraped_at)
                        for n in notes
                        if n.scraped_at
                    ]
                )
                if len(dates) >= 2:
                    span_days = (dates[-1] - dates[0]).days or 1
                    freq = len(notes) / (span_days / 7)
                    comp.posting_frequency = f"{freq:.0f}/week"
            except (ValueError, TypeError):
                pass

        self.save()
        return comp

    def compute_all_stats(self) -> None:
        """Compute stats for all competitors."""
        for comp in self.competitors:
            self.compute_competitor_stats(comp.user_id)

    # ------------------------------------------------------------------
    # AI-powered analysis
    # ------------------------------------------------------------------

    def analyze_title_patterns(
        self, notes: list[ScrapedNote] | None = None
    ) -> dict[str, Any]:
        """Use AI to analyze title patterns from top-performing notes."""
        if not self.ai:
            logger.warning("AI client not available for title analysis")
            return {}

        if notes is None:
            notes = []
            for user_notes in self.all_notes.values():
                notes.extend(user_notes)

        # Sort by engagement and take top 50
        notes.sort(key=lambda n: n.total_interactions, reverse=True)
        top_notes = notes[:50]

        if not top_notes:
            return {}

        titles_text = "\n".join(
            f"- [{n.total_interactions}赞藏评] {n.title}" for n in top_notes
        )

        prompt = TITLE_PATTERN_PROMPT.format(titles=titles_text)
        data = self.ai.chat_json(
            prompt,
            system="你是一位小红书内容分析专家。请始终返回有效的JSON。",
        )
        return data if isinstance(data, dict) else {}

    def analyze_competitor_style(
        self, user_id: str
    ) -> dict[str, Any]:
        """Use AI to analyze a competitor's content style."""
        if not self.ai:
            logger.warning("AI client not available for style analysis")
            return {}

        comp = next((c for c in self.competitors if c.user_id == user_id), None)
        notes = self.all_notes.get(user_id, [])

        if not comp or not notes:
            return {}

        # Take top 10 notes for analysis
        sorted_notes = sorted(notes, key=lambda n: n.total_interactions, reverse=True)
        top_notes = sorted_notes[:10]

        notes_text = "\n\n".join(
            f"### [{n.total_interactions}互动 | 赞{n.likes} 藏{n.saves} 评{n.comments}]\n"
            f"标题: {n.title}\n"
            f"内容: {n.body[:300]}..."
            for n in top_notes
        )

        prompt = CONTENT_STYLE_PROMPT.format(
            nickname=comp.nickname,
            followers=comp.followers,
            vertical=comp.vertical or "未知",
            notes_text=notes_text,
        )

        data = self.ai.chat_json(
            prompt,
            system="你是一位自媒体内容策略分析师。请始终返回有效的JSON。",
        )

        if isinstance(data, dict):
            comp.content_style = data.get("writing_style", "")
            self.save()

        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # Benchmark report
    # ------------------------------------------------------------------

    def generate_report(self) -> BenchmarkReport:
        """Generate a full benchmark report across all competitors."""
        self.compute_all_stats()

        # Collect all notes sorted by engagement
        all_notes = []
        for notes in self.all_notes.values():
            all_notes.extend(notes)
        all_notes.sort(key=lambda n: n.total_interactions, reverse=True)

        # Title pattern analysis
        title_analysis = self.analyze_title_patterns(all_notes) if self.ai else {}

        # Aggregate best tags
        all_tags: list[str] = []
        for comp in self.competitors:
            all_tags.extend(comp.common_tags)
        best_tags = [tag for tag, _ in Counter(all_tags).most_common(30)]

        # Build report
        report = BenchmarkReport(
            competitors=self.competitors,
            top_performing_notes=all_notes[:20],
            title_patterns=title_analysis.get("title_patterns", []),
            content_patterns=[],
            best_tags=best_tags,
            avg_save_like_ratio=(
                sum(c.avg_save_like_ratio for c in self.competitors)
                / len(self.competitors)
                if self.competitors
                else 0
            ),
        )

        # AI-powered summary
        if self.ai and self.competitors:
            summary_data = self._generate_ai_summary()
            report.recommendations = summary_data.get("action_items", [])
            report.content_patterns = summary_data.get("common_viral_traits", [])

        return report

    def _generate_ai_summary(self) -> dict[str, Any]:
        """Generate AI-powered benchmark summary."""
        if not self.ai:
            return {}

        summaries = []
        for comp in self.competitors:
            notes = self.all_notes.get(comp.user_id, [])
            top_titles = [n.title for n in sorted(
                notes, key=lambda n: n.total_interactions, reverse=True
            )[:5]]

            summaries.append(
                f"### {comp.nickname}\n"
                f"- 粉丝: {comp.followers:,}\n"
                f"- 笔记数: {comp.total_notes}\n"
                f"- 平均赞: {comp.avg_likes:.0f}\n"
                f"- 平均藏: {comp.avg_saves:.0f}\n"
                f"- 收藏赞比: {comp.avg_save_like_ratio:.2f}\n"
                f"- 爆款率: {comp.viral_rate:.1%}\n"
                f"- 发布频率: {comp.posting_frequency}\n"
                f"- 高赞标题: {', '.join(top_titles)}\n"
            )

        prompt = BENCHMARK_SUMMARY_PROMPT.format(
            competitor_summaries="\n".join(summaries)
        )

        data = self.ai.chat_json(
            prompt,
            system="你是一位自媒体矩阵运营专家。请始终返回有效的JSON。",
        )
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # Output for pipeline integration
    # ------------------------------------------------------------------

    def get_topic_insights(self) -> dict[str, Any]:
        """Get competitor insights formatted for topic research step.

        Returns data that can be injected into the TopicResearchStep context
        to inform topic selection based on competitor analysis.
        """
        if not self.competitors:
            return {"has_benchmark": False}

        # Top performing titles across all competitors
        all_notes = []
        for notes in self.all_notes.values():
            all_notes.extend(notes)
        all_notes.sort(key=lambda n: n.total_interactions, reverse=True)

        top_titles = [
            {"title": n.title, "interactions": n.total_interactions}
            for n in all_notes[:20]
        ]

        # Best tags
        all_tags: list[str] = []
        for comp in self.competitors:
            all_tags.extend(comp.common_tags[:10])
        best_tags = [tag for tag, _ in Counter(all_tags).most_common(15)]

        # Average benchmarks
        avg_viral_rate = (
            sum(c.viral_rate for c in self.competitors) / len(self.competitors)
            if self.competitors
            else 0
        )

        return {
            "has_benchmark": True,
            "competitor_count": len(self.competitors),
            "top_performing_titles": top_titles,
            "best_tags": best_tags,
            "avg_viral_rate": avg_viral_rate,
            "total_notes_analyzed": len(all_notes),
        }

    def get_competitor_summary_text(self) -> str:
        """Get a text summary of competitors for prompt injection."""
        if not self.competitors:
            return ""

        lines = ["## 对标账号数据\n"]
        for comp in self.competitors:
            notes = self.all_notes.get(comp.user_id, [])
            top = sorted(notes, key=lambda n: n.total_interactions, reverse=True)[:3]
            top_titles = ", ".join(f"「{n.title}」({n.total_interactions}互动)" for n in top)

            lines.append(
                f"**{comp.nickname}** ({comp.vertical}): "
                f"爆款率{comp.viral_rate:.0%}, "
                f"藏赞比{comp.avg_save_like_ratio:.2f}, "
                f"高赞内容: {top_titles}"
            )

        return "\n".join(lines)
