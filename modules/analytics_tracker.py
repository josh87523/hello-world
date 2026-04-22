"""Analytics tracking and performance iteration engine.

Tracks published content performance across all matrix accounts,
identifies patterns in what drives viral content (1000+ interactions),
and generates actionable insights for the next content cycle.

Key metrics from research:
- save/like ratio > 1.0 signals extreme viral potential
- Click-through rate > 8% needed to escape cold-start pool
- Engagement rate > 5% needed for continued algorithmic push
- 收藏权重 > 评论权重 > 点赞权重 (XHS algorithm weighting)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

ANALYTICS_FILE = "data/analytics.json"


@dataclass
class ContentRecord:
    """A record of published content and its performance."""

    content_id: str
    account_id: str
    title: str
    vertical: str
    topic: str
    quality_score: float
    published_at: str
    # Performance metrics (updated after publishing)
    likes: int = 0
    saves: int = 0
    comments: int = 0
    shares: int = 0
    views: int = 0
    # Calculated
    save_like_ratio: float = 0.0
    engagement_rate: float = 0.0
    is_viral: bool = False  # 1000+ total interactions

    def update_metrics(
        self,
        likes: int = 0,
        saves: int = 0,
        comments: int = 0,
        shares: int = 0,
        views: int = 0,
    ) -> None:
        self.likes = likes
        self.saves = saves
        self.comments = comments
        self.shares = shares
        self.views = views
        self.save_like_ratio = saves / likes if likes > 0 else 0
        total_interactions = likes + saves + comments + shares
        self.engagement_rate = total_interactions / views if views > 0 else 0
        self.is_viral = total_interactions >= 1000


class AnalyticsTracker:
    """Tracks content performance and identifies patterns for optimization.

    After each publishing cycle, performance data is fed back into the system
    to inform topic selection, cover strategy, and content structure decisions.
    """

    def __init__(self, data_file: str = ANALYTICS_FILE):
        self.data_file = data_file
        self.records: list[ContentRecord] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for r in data.get("records", []):
                    self.records.append(ContentRecord(**r))

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.data_file) or ".", exist_ok=True)
        data = {
            "records": [r.__dict__ for r in self.records],
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_record(self, record: ContentRecord) -> None:
        self.records.append(record)
        self._save()

    def update_performance(self, content_id: str, **metrics: Any) -> None:
        for r in self.records:
            if r.content_id == content_id:
                r.update_metrics(**metrics)
                self._save()
                return
        logger.warning("Content %s not found in analytics", content_id)

    def get_viral_rate(self, account_id: str | None = None) -> float:
        """Percentage of content that reached 1000+ interactions."""
        records = self.records
        if account_id:
            records = [r for r in records if r.account_id == account_id]
        if not records:
            return 0.0
        return sum(1 for r in records if r.is_viral) / len(records)

    def get_best_verticals(self, top_n: int = 3) -> list[dict[str, Any]]:
        """Identify which content verticals perform best."""
        vertical_stats: dict[str, dict[str, int]] = {}

        for r in self.records:
            if r.vertical not in vertical_stats:
                vertical_stats[r.vertical] = {
                    "total": 0,
                    "viral": 0,
                    "total_interactions": 0,
                    "saves": 0,
                    "likes": 0,
                }

            stats = vertical_stats[r.vertical]
            stats["total"] += 1
            stats["viral"] += 1 if r.is_viral else 0
            stats["total_interactions"] += r.likes + r.saves + r.comments + r.shares
            stats["saves"] += r.saves
            stats["likes"] += r.likes

        results = []
        for vertical, stats in vertical_stats.items():
            avg_interactions = (
                stats["total_interactions"] / stats["total"] if stats["total"] else 0
            )
            save_like = stats["saves"] / stats["likes"] if stats["likes"] else 0
            results.append(
                {
                    "vertical": vertical,
                    "total_posts": stats["total"],
                    "viral_count": stats["viral"],
                    "viral_rate": (
                        stats["viral"] / stats["total"] if stats["total"] else 0
                    ),
                    "avg_interactions": avg_interactions,
                    "save_like_ratio": save_like,
                }
            )

        results.sort(key=lambda x: x["avg_interactions"], reverse=True)
        return results[:top_n]

    def get_best_posting_times(self) -> list[dict[str, Any]]:
        """Analyze which posting times get the best engagement."""
        time_stats: dict[str, dict[str, int]] = {}

        for r in self.records:
            if not r.published_at:
                continue
            try:
                hour = datetime.fromisoformat(r.published_at).strftime("%H:00")
            except (ValueError, TypeError):
                continue

            if hour not in time_stats:
                time_stats[hour] = {"total": 0, "interactions": 0, "viral": 0}

            time_stats[hour]["total"] += 1
            time_stats[hour]["interactions"] += r.likes + r.saves + r.comments
            time_stats[hour]["viral"] += 1 if r.is_viral else 0

        results = []
        for hour, stats in time_stats.items():
            results.append(
                {
                    "hour": hour,
                    "posts": stats["total"],
                    "avg_interactions": (
                        stats["interactions"] / stats["total"] if stats["total"] else 0
                    ),
                    "viral_rate": (
                        stats["viral"] / stats["total"] if stats["total"] else 0
                    ),
                }
            )

        results.sort(key=lambda x: x["avg_interactions"], reverse=True)
        return results

    def get_iteration_insights(self) -> dict[str, Any]:
        """Generate actionable insights for the next content cycle.

        This is the core feedback loop: analyze what worked, recommend
        adjustments to verticals, posting times, and content patterns.
        """
        if len(self.records) < 5:
            return {
                "status": "insufficient_data",
                "message": "需要至少5条发布记录才能生成洞察",
                "recommendation": "继续发布内容，积累数据",
            }

        best_verticals = self.get_best_verticals(3)
        best_times = self.get_best_posting_times()
        viral_rate = self.get_viral_rate()

        # Find high save/like ratio patterns
        high_save_records = sorted(
            self.records, key=lambda r: r.save_like_ratio, reverse=True
        )[:5]
        high_save_topics = [
            r.topic for r in high_save_records if r.save_like_ratio > 0
        ]

        return {
            "status": "ready",
            "viral_rate": viral_rate,
            "best_verticals": best_verticals,
            "best_posting_times": best_times[:3] if best_times else [],
            "high_save_topics": high_save_topics,
            "total_records": len(self.records),
            "recommendation": self._generate_recommendation(
                best_verticals, viral_rate
            ),
        }

    def _generate_recommendation(
        self, best_verticals: list[dict[str, Any]], viral_rate: float
    ) -> str:
        if viral_rate >= 0.3:
            return "爆款率已达30%+，保持当前策略，可尝试扩展新垂类"
        elif viral_rate >= 0.1:
            top = best_verticals[0]["vertical"] if best_verticals else "unknown"
            return f"建议加大 {top} 垂类的产出，该垂类数据最好"
        else:
            return "爆款率较低，建议优化标题和封面策略，参考高收藏率内容的选题模式"

    def get_summary(self) -> dict[str, Any]:
        total = len(self.records)
        viral = sum(1 for r in self.records if r.is_viral)
        total_interactions = sum(
            r.likes + r.saves + r.comments + r.shares for r in self.records
        )

        return {
            "total_posts": total,
            "viral_posts": viral,
            "viral_rate": viral / total if total else 0,
            "total_interactions": total_interactions,
            "avg_interactions": total_interactions / total if total else 0,
        }
