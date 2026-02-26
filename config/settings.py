"""Global configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AIConfig:
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096

    @classmethod
    def from_env(cls) -> AIConfig:
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("AI_MODEL", cls.model),
        )


@dataclass
class FeishuConfig:
    app_id: str = ""
    app_secret: str = ""
    folder_token: str = ""
    bot_webhook: str = ""

    @classmethod
    def from_env(cls) -> FeishuConfig:
        return cls(
            app_id=os.getenv("FEISHU_APP_ID", ""),
            app_secret=os.getenv("FEISHU_APP_SECRET", ""),
            folder_token=os.getenv("FEISHU_FOLDER_TOKEN", ""),
            bot_webhook=os.getenv("FEISHU_BOT_WEBHOOK", ""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret)


@dataclass
class WorkflowConfig:
    """Main workflow configuration."""

    domains: list[str] = field(default_factory=lambda: ["ai", "创业", "写作"])
    platform: str = "xiaohongshu"
    daily_count: int = 1
    schedule_time: str = "08:00"
    quality_threshold: float = 0.75
    optimization_rounds: int = 1

    @classmethod
    def from_env(cls) -> WorkflowConfig:
        domains_str = os.getenv("CONTENT_DOMAINS", "ai,创业,写作")
        return cls(
            domains=domains_str.split(","),
            platform=os.getenv("PLATFORM", cls.platform),
            daily_count=int(os.getenv("DAILY_COUNT", cls.daily_count)),
            schedule_time=os.getenv("SCHEDULE_TIME", cls.schedule_time),
            quality_threshold=float(
                os.getenv("QUALITY_THRESHOLD", cls.quality_threshold)
            ),
        )


@dataclass
class MatrixConfig:
    """Matrix account management configuration."""

    enabled: bool = False
    state_file: str = "data/matrix_state.json"
    analytics_file: str = "data/analytics.json"
    cover_variants: int = 3

    @classmethod
    def from_env(cls) -> MatrixConfig:
        return cls(
            enabled=os.getenv("MATRIX_ENABLED", "false").lower() == "true",
            state_file=os.getenv("MATRIX_STATE_FILE", cls.state_file),
            analytics_file=os.getenv("ANALYTICS_FILE", cls.analytics_file),
            cover_variants=int(os.getenv("COVER_VARIANTS", cls.cover_variants)),
        )


@dataclass
class ScraperConfig:
    """XHS scraper configuration."""

    cookie: str = ""
    rate_limit: float = 2.0
    max_notes_per_search: int = 40
    max_notes_per_user: int = 50
    data_dir: str = "data/scraper"
    benchmark_file: str = "data/benchmark.json"

    @classmethod
    def from_env(cls) -> ScraperConfig:
        return cls(
            cookie=os.getenv("XHS_COOKIE", ""),
            rate_limit=float(os.getenv("XHS_RATE_LIMIT", "2.0")),
            max_notes_per_search=int(os.getenv("XHS_MAX_SEARCH", "40")),
            max_notes_per_user=int(os.getenv("XHS_MAX_USER_NOTES", "50")),
            data_dir=os.getenv("XHS_DATA_DIR", cls.data_dir),
            benchmark_file=os.getenv("BENCHMARK_FILE", cls.benchmark_file),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.cookie)


@dataclass
class AppConfig:
    """Top-level app configuration."""

    ai: AIConfig = field(default_factory=AIConfig)
    feishu: FeishuConfig = field(default_factory=FeishuConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    matrix: MatrixConfig = field(default_factory=MatrixConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            ai=AIConfig.from_env(),
            feishu=FeishuConfig.from_env(),
            workflow=WorkflowConfig.from_env(),
            matrix=MatrixConfig.from_env(),
            scraper=ScraperConfig.from_env(),
        )
