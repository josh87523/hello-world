"""Matrix account management for multi-account content operations.

Manages multiple Xiaohongshu accounts, each with its own persona, content
vertical, and posting schedule. Enables parallel content production across
specialized niches.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

MATRIX_STATE_FILE = "data/matrix_state.json"


@dataclass
class AccountPersona:
    """A matrix account with its own persona, vertical, and posting schedule."""

    account_id: str
    name: str
    vertical: str
    domains: list[str] = field(default_factory=list)
    tone: str = "友好专业"
    posting_times: list[str] = field(default_factory=lambda: ["08:00", "12:00", "20:00"])
    daily_count: int = 2
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatrixState:
    """Persistent state for all matrix accounts."""

    accounts: list[AccountPersona] = field(default_factory=list)
    content_log: list[dict[str, Any]] = field(default_factory=list)
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "accounts": [
                {
                    "account_id": a.account_id,
                    "name": a.name,
                    "vertical": a.vertical,
                    "domains": a.domains,
                    "tone": a.tone,
                    "posting_times": a.posting_times,
                    "daily_count": a.daily_count,
                    "active": a.active,
                    "metadata": a.metadata,
                }
                for a in self.accounts
            ],
            "content_log": self.content_log[-500:],
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MatrixState:
        accounts = []
        for a in data.get("accounts", []):
            accounts.append(
                AccountPersona(
                    account_id=a["account_id"],
                    name=a["name"],
                    vertical=a["vertical"],
                    domains=a.get("domains", []),
                    tone=a.get("tone", "友好专业"),
                    posting_times=a.get("posting_times", ["08:00", "12:00", "20:00"]),
                    daily_count=a.get("daily_count", 2),
                    active=a.get("active", True),
                    metadata=a.get("metadata", {}),
                )
            )
        return cls(
            accounts=accounts,
            content_log=data.get("content_log", []),
            last_updated=data.get("last_updated", ""),
        )


class MatrixManager:
    """Manages multi-account content operations.

    Each account has a specialized vertical (ai_tools, ai_tutorial, etc.)
    and its own persona, tone, and posting schedule. The matrix approach
    increases total output volume and diversifies content risk.
    """

    def __init__(self, state_file: str = MATRIX_STATE_FILE):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> MatrixState:
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                return MatrixState.from_dict(json.load(f))
        return self._create_default_state()

    def save(self) -> None:
        self.state.last_updated = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)

    def _create_default_state(self) -> MatrixState:
        """Create default matrix with 5 specialized accounts."""
        default_accounts = [
            AccountPersona(
                account_id="matrix_01",
                name="AI工具实验室",
                vertical="ai_tools",
                domains=["ai工具", "效率提升", "科技"],
                tone="极客+接地气",
                daily_count=2,
            ),
            AccountPersona(
                account_id="matrix_02",
                name="AI创作手册",
                vertical="ai_tutorial",
                domains=["ai教程", "写作", "创作"],
                tone="耐心的老师",
                daily_count=2,
            ),
            AccountPersona(
                account_id="matrix_03",
                name="AI前沿观察",
                vertical="ai_insight",
                domains=["ai行业", "科技趋势", "深度分析"],
                tone="冷静分析师",
                daily_count=1,
            ),
            AccountPersona(
                account_id="matrix_04",
                name="AI副业日记",
                vertical="ai_monetization",
                domains=["ai赚钱", "副业", "自由职业"],
                tone="真实分享者",
                daily_count=2,
            ),
            AccountPersona(
                account_id="matrix_05",
                name="AI灵感工坊",
                vertical="ai_creative",
                domains=["ai创意", "设计", "灵感"],
                tone="有品味的创作者",
                daily_count=1,
            ),
        ]
        return MatrixState(accounts=default_accounts)

    def get_active_accounts(self) -> list[AccountPersona]:
        return [a for a in self.state.accounts if a.active]

    def get_account(self, account_id: str) -> AccountPersona | None:
        for a in self.state.accounts:
            if a.account_id == account_id:
                return a
        return None

    def get_daily_schedule(self) -> list[dict[str, Any]]:
        """Get today's full content schedule across all active accounts.

        Returns a list of scheduled content slots sorted by posting time,
        with each slot specifying the account, vertical, domains, and tone.
        """
        schedule = []
        for account in self.get_active_accounts():
            times = account.posting_times[: account.daily_count]
            for posting_time in times:
                schedule.append(
                    {
                        "account_id": account.account_id,
                        "account_name": account.name,
                        "vertical": account.vertical,
                        "domains": account.domains,
                        "tone": account.tone,
                        "posting_time": posting_time,
                    }
                )
        schedule.sort(key=lambda x: x["posting_time"])
        return schedule

    def log_content(self, account_id: str, content_data: dict[str, Any]) -> None:
        """Log a generated content piece for tracking."""
        self.state.content_log.append(
            {
                "account_id": account_id,
                "timestamp": datetime.now().isoformat(),
                **content_data,
            }
        )
        self.save()

    def get_account_stats(self, account_id: str) -> dict[str, Any]:
        """Get production stats for an account."""
        entries = [
            e for e in self.state.content_log if e.get("account_id") == account_id
        ]
        if not entries:
            return {"total": 0, "avg_quality": 0, "passed": 0, "pass_rate": 0}

        scores = [
            e.get("quality_score", 0) for e in entries if e.get("quality_score")
        ]
        passed = sum(1 for e in entries if e.get("status") == "approved")

        return {
            "total": len(entries),
            "avg_quality": sum(scores) / len(scores) if scores else 0,
            "passed": passed,
            "pass_rate": passed / len(entries) if entries else 0,
        }

    def get_total_daily_output(self) -> int:
        """Total pieces of content scheduled per day across all accounts."""
        return sum(a.daily_count for a in self.get_active_accounts())

    def add_account(self, account: AccountPersona) -> None:
        self.state.accounts.append(account)
        self.save()
