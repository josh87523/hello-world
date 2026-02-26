"""Social Media AI Workflow - Main entry point.

自媒体 AI 工作流：从选题到发布的全自动化内容生产系统。

Usage:
    # 单次生成
    python main.py run

    # 指定话题生成
    python main.py run --topic "AI Agent 正在替代程序员？"

    # 定时任务模式
    python main.py schedule

    # 生成多篇
    python main.py run --count 3
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from ai.client import AIClient
from config.settings import AppConfig
from core.scheduler import Scheduler
from core.workflow import ContentWorkflow
from integrations.feishu import FeishuClient
from models.content import Platform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Platform name to enum mapping
PLATFORM_MAP = {p.value: p for p in Platform}


def build_workflow(config: AppConfig, dry_run: bool = False) -> ContentWorkflow:
    """Build the workflow from configuration."""
    if dry_run:
        from ai.mock import MockAIClient

        ai_client = MockAIClient()
    else:
        ai_client = AIClient(
            api_key=config.ai.api_key,
            model=config.ai.model,
        )

    feishu_client = None
    if config.feishu.is_configured:
        feishu_client = FeishuClient(
            app_id=config.feishu.app_id,
            app_secret=config.feishu.app_secret,
            folder_token=config.feishu.folder_token,
        )

    platform = PLATFORM_MAP.get(config.workflow.platform, Platform.XIAOHONGSHU)

    return ContentWorkflow(
        ai_client=ai_client,
        platform=platform,
        feishu_client=feishu_client,
    )


def cmd_run(args: argparse.Namespace, config: AppConfig) -> None:
    """Run the content workflow once."""
    workflow = build_workflow(config, dry_run=args.dry_run)

    results = workflow.run(
        domains=config.workflow.domains,
        count=args.count,
        custom_topic=args.topic,
    )

    for i, result in enumerate(results):
        success = result.get("pipeline_success", False)
        final = result.get("final_content")

        print(f"\n{'='*60}")
        print(f"Content {i+1}/{len(results)} - {'SUCCESS' if success else 'FAILED'}")
        print(f"{'='*60}")

        if final:
            print(f"Title: {final.title}")
            print(f"Quality: {final.quality_score:.2f}")
            print(f"Status: {final.status.value}")
            print(f"\n{final.body[:500]}...")
            if final.tags:
                print(f"\nTags: {' '.join(final.tags)}")
            if final.feishu_doc_url:
                print(f"\nFeishu Doc: {final.feishu_doc_url}")

        if result.get("errors"):
            print(f"\nErrors: {result['errors']}")

    # Output full JSON for programmatic use
    if args.json:
        output = []
        for r in results:
            final = r.get("final_content")
            if final:
                output.append(final.to_dict())
        print(f"\n--- JSON OUTPUT ---\n{json.dumps(output, ensure_ascii=False, indent=2)}")


def cmd_schedule(args: argparse.Namespace, config: AppConfig) -> None:
    """Start the scheduler for daily content generation."""
    workflow = build_workflow(config)
    scheduler = Scheduler()

    scheduler.add_job(
        name="daily_content",
        func=workflow.run,
        cron=config.workflow.schedule_time,
        kwargs={
            "domains": config.workflow.domains,
            "count": config.workflow.daily_count,
        },
    )

    print(f"Scheduler started. Daily content at {config.workflow.schedule_time}")
    print(f"Domains: {', '.join(config.workflow.domains)}")
    print(f"Platform: {config.workflow.platform}")
    print(f"Count: {config.workflow.daily_count}/day")
    print("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.stop()
        print("\nScheduler stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="自媒体 AI 工作流 - 全自动内容生产系统",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run command
    run_parser = subparsers.add_parser("run", help="运行一次内容生成")
    run_parser.add_argument("--topic", "-t", help="指定话题（不指定则自动选题）")
    run_parser.add_argument("--count", "-n", type=int, default=1, help="生成篇数")
    run_parser.add_argument("--json", action="store_true", help="输出JSON格式")
    run_parser.add_argument("--dry-run", action="store_true", help="使用模拟数据测试（不调用API）")

    # schedule command
    subparsers.add_parser("schedule", help="启动定时任务模式")

    args = parser.parse_args()
    config = AppConfig.from_env()

    is_dry_run = args.command == "run" and getattr(args, "dry_run", False)
    if not config.ai.api_key and not is_dry_run:
        print("Error: ANTHROPIC_API_KEY not set. See .env.example for configuration.")
        sys.exit(1)

    if args.command == "run":
        cmd_run(args, config)
    elif args.command == "schedule":
        cmd_schedule(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
