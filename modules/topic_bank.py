"""选题库管理 - 持久化存储对标笔记，按策略挑选爆款做二创素材。

选题库 = 对标账号的爬取笔记集合，每条笔记附带使用状态。
存储：data/topic_bank.json
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from models.competitor import ScrapedNote

logger = logging.getLogger(__name__)


@dataclass
class TopicBankEntry:
    """选题库中的一条记录：ScrapedNote + 使用状态。"""

    note: ScrapedNote
    source_account: str = ""
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    used: bool = False
    used_at: str = ""
    used_by_content_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "note": self.note.to_dict(),
            "source_account": self.source_account,
            "added_at": self.added_at,
            "used": self.used,
            "used_at": self.used_at,
            "used_by_content_id": self.used_by_content_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TopicBankEntry:
        note = ScrapedNote.from_dict(data["note"])
        return cls(
            note=note,
            source_account=data.get("source_account", ""),
            added_at=data.get("added_at", ""),
            used=data.get("used", False),
            used_at=data.get("used_at", ""),
            used_by_content_id=data.get("used_by_content_id", ""),
        )


class TopicBank:
    """选题库管理器。"""

    def __init__(self, bank_file: str = "data/topic_bank.json"):
        self.bank_file = bank_file
        self.entries: list[TopicBankEntry] = []
        self._load()

    # --- 入库 ---

    def ingest_from_competitor(
        self, user_id: str, notes: list[ScrapedNote]
    ) -> int:
        """将对标账号的爬取笔记批量入库，按 note_id 去重。返回新增数量。"""
        existing_ids = {e.note.note_id for e in self.entries}
        added = 0
        for note in notes:
            if note.note_id in existing_ids:
                continue
            note.compute_metrics()
            self.entries.append(
                TopicBankEntry(note=note, source_account=user_id)
            )
            existing_ids.add(note.note_id)
            added += 1
        if added:
            self.save()
            logger.info("Ingested %d notes from competitor %s", added, user_id)
        return added

    def ingest_from_scraper(
        self, notes: list[ScrapedNote], source: str = "search"
    ) -> int:
        """将搜索/导入的笔记批量入库。"""
        return self.ingest_from_competitor(source, notes)

    # --- 选题 ---

    def select_topic(
        self,
        strategy: str = "viral_unused",
        vertical: str = "",
        count: int = 1,
    ) -> list[TopicBankEntry]:
        """按策略从选题库挑选笔记。

        策略:
        - viral_unused: 按互动量排序，优先未使用的 (默认)
        - high_save_ratio: 按收藏/赞比排序
        - recent_viral: 最近入库 + 高互动量
        """
        candidates = [e for e in self.entries if not e.used]

        if not candidates:
            logger.warning("选题库中所有选题已被使用")
            return []

        if strategy == "high_save_ratio":
            candidates.sort(key=lambda e: e.note.save_like_ratio, reverse=True)
        elif strategy == "recent_viral":
            candidates.sort(
                key=lambda e: (e.added_at, e.note.total_interactions),
                reverse=True,
            )
        else:  # viral_unused
            candidates.sort(
                key=lambda e: e.note.total_interactions, reverse=True
            )

        return candidates[:count]

    def mark_used(self, note_id: str, content_id: str = "") -> None:
        """标记某条笔记已被使用。"""
        for entry in self.entries:
            if entry.note.note_id == note_id:
                entry.used = True
                entry.used_at = datetime.now().isoformat()
                entry.used_by_content_id = content_id
                self.save()
                return

    # --- 查询 ---

    def get_stats(self) -> dict[str, Any]:
        used = sum(1 for e in self.entries if e.used)
        return {
            "total": len(self.entries),
            "used": used,
            "unused": len(self.entries) - used,
            "sources": list({e.source_account for e in self.entries}),
        }

    def get_unused_count(self) -> int:
        return sum(1 for e in self.entries if not e.used)

    # --- 持久化 ---

    def _load(self) -> None:
        if not os.path.exists(self.bank_file):
            return
        try:
            with open(self.bank_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [
                TopicBankEntry.from_dict(e) for e in data.get("entries", [])
            ]
            logger.info("Loaded topic bank: %d entries", len(self.entries))
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to load topic bank: %s", e)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.bank_file) or ".", exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "total": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
        }
        with open(self.bank_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
