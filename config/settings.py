"""Global configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AIConfig:
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-max"
    temperature: float = 0.7
    max_tokens: int = 4096

    @classmethod
    def from_env(cls) -> AIConfig:
        return cls(
            api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            base_url=os.getenv("AI_BASE_URL", cls.base_url),
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
    daily_count: int = 1  # how many posts per day
    schedule_time: str = "08:00"  # when to run daily
    quality_threshold: float = 0.7
    optimization_rounds: int = 1

    @classmethod
    def from_env(cls) -> WorkflowConfig:
        domains_str = os.getenv("CONTENT_DOMAINS", "ai,创业,写作")
        return cls(
            domains=domains_str.split(","),
            platform=os.getenv("PLATFORM", cls.platform),
            daily_count=int(os.getenv("DAILY_COUNT", cls.daily_count)),
            schedule_time=os.getenv("SCHEDULE_TIME", cls.schedule_time),
            quality_threshold=float(os.getenv("QUALITY_THRESHOLD", cls.quality_threshold)),
        )


@dataclass
class AppConfig:
    """Top-level app configuration."""

    ai: AIConfig = field(default_factory=AIConfig)
    feishu: FeishuConfig = field(default_factory=FeishuConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            ai=AIConfig.from_env(),
            feishu=FeishuConfig.from_env(),
            workflow=WorkflowConfig.from_env(),
        )
