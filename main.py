"""Social Media AI Workflow - Main entry point.

自媒体 AI 工作流：从选题到发布的全自动化内容生产系统。
支持矩阵号运营、封面策略、数据追踪与迭代优化。

Usage:
    # 单次生成
    python main.py run

    # 指定话题生成
    python main.py run --topic "AI Agent 正在替代程序员？"

    # 生成多篇
    python main.py run --count 3

    # 矩阵模式：全部账号批量生成
    python main.py matrix

    # 矩阵模式：指定账号
    python main.py matrix --account matrix_01

    # 查看矩阵状态
    python main.py matrix --status

    # 查看数据分析
    python main.py analytics

    # 更新内容表现数据
    python main.py analytics --update <content_id> --likes 500 --saves 300 --comments 80

    # 定时任务模式
    python main.py schedule
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
from modules.analytics_tracker import AnalyticsTracker, ContentRecord
from modules.matrix_manager import MatrixManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PLATFORM_MAP = {p.value: p for p in Platform}


def build_ai_client(config: AppConfig, dry_run: bool = False) -> AIClient:
    """Build the AI client from configuration."""
    if dry_run:
        from ai.mock import MockAIClient

        return MockAIClient()
    return AIClient(api_key=config.ai.api_key, model=config.ai.model)


def build_workflow(config: AppConfig, dry_run: bool = False) -> ContentWorkflow:
    """Build the workflow from configuration."""
    ai_client = build_ai_client(config, dry_run)

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
        cover_variants=config.matrix.cover_variants,
    )


def cmd_run(args: argparse.Namespace, config: AppConfig) -> None:
    """Run the content workflow once."""
    workflow = build_workflow(config, dry_run=args.dry_run)

    results = workflow.run(
        domains=config.workflow.domains,
        count=args.count,
        custom_topic=args.topic,
    )

    _print_results(results, json_output=args.json)


def cmd_matrix(args: argparse.Namespace, config: AppConfig) -> None:
    """Run content generation across matrix accounts."""
    manager = MatrixManager(state_file=config.matrix.state_file)

    if args.status:
        _print_matrix_status(manager)
        return

    ai_client = build_ai_client(config, dry_run=args.dry_run)
    platform = PLATFORM_MAP.get(config.workflow.platform, Platform.XIAOHONGSHU)
    tracker = AnalyticsTracker(data_file=config.matrix.analytics_file)

    feishu_client = None
    if config.feishu.is_configured:
        feishu_client = FeishuClient(
            app_id=config.feishu.app_id,
            app_secret=config.feishu.app_secret,
            folder_token=config.feishu.folder_token,
        )

    # Filter to specific account if requested
    if args.account:
        account = manager.get_account(args.account)
        if not account:
            print(f"Error: Account '{args.account}' not found.")
            print(f"Available: {[a.account_id for a in manager.state.accounts]}")
            sys.exit(1)
        accounts = [account]
    else:
        accounts = manager.get_active_accounts()

    if not accounts:
        print("No active matrix accounts found.")
        sys.exit(1)

    print(f"Running matrix mode: {len(accounts)} accounts")
    print(f"{'='*60}")

    all_results = []
    for account in accounts:
        print(f"\n--- Account: {account.name} ({account.account_id}) ---")
        print(f"    Vertical: {account.vertical} | Tone: {account.tone}")
        print(f"    Domains: {', '.join(account.domains)}")

        workflow = ContentWorkflow(
            ai_client=ai_client,
            platform=platform,
            feishu_client=feishu_client,
            cover_variants=config.matrix.cover_variants,
        )

        count = args.count if args.count else account.daily_count
        results = workflow.run(
            domains=account.domains,
            count=count,
            account_tone=account.tone,
            account_vertical=account.vertical,
            account_id=account.account_id,
        )

        for result in results:
            final = result.get("final_content")
            if final:
                # Log to matrix manager
                manager.log_content(
                    account.account_id,
                    {
                        "content_id": final.id,
                        "title": final.title,
                        "quality_score": final.quality_score,
                        "status": final.status.value,
                        "vertical": account.vertical,
                    },
                )

                # Log to analytics tracker
                tracker.add_record(
                    ContentRecord(
                        content_id=final.id,
                        account_id=account.account_id,
                        title=final.title,
                        vertical=account.vertical,
                        topic=final.draft.idea.topic,
                        quality_score=final.quality_score,
                        published_at=final.created_at.isoformat(),
                    )
                )

        all_results.extend(results)

    print(f"\n{'='*60}")
    print(f"Matrix run complete: {len(all_results)} pieces generated")
    _print_results(all_results, json_output=args.json)


def cmd_analytics(args: argparse.Namespace, config: AppConfig) -> None:
    """View analytics or update performance data."""
    tracker = AnalyticsTracker(data_file=config.matrix.analytics_file)

    if args.update:
        tracker.update_performance(
            content_id=args.update,
            likes=args.likes or 0,
            saves=args.saves or 0,
            comments=args.comments or 0,
            shares=args.shares or 0,
            views=args.views or 0,
        )
        print(f"Updated performance data for content: {args.update}")
        return

    # Show analytics dashboard
    summary = tracker.get_summary()
    insights = tracker.get_iteration_insights()

    print(f"\n{'='*60}")
    print("ANALYTICS DASHBOARD")
    print(f"{'='*60}")

    print(f"\nTotal posts: {summary['total_posts']}")
    print(f"Viral posts (1000+ interactions): {summary['viral_posts']}")
    print(f"Viral rate: {summary['viral_rate']:.1%}")
    print(f"Total interactions: {summary['total_interactions']:,}")
    print(f"Avg interactions/post: {summary['avg_interactions']:.0f}")

    if insights.get("status") == "ready":
        print(f"\n--- Best Verticals ---")
        for v in insights.get("best_verticals", []):
            print(
                f"  {v['vertical']}: {v['total_posts']} posts, "
                f"viral rate {v['viral_rate']:.1%}, "
                f"avg {v['avg_interactions']:.0f} interactions, "
                f"save/like {v['save_like_ratio']:.2f}"
            )

        print(f"\n--- Best Posting Times ---")
        for t in insights.get("best_posting_times", []):
            print(
                f"  {t['hour']}: {t['posts']} posts, "
                f"avg {t['avg_interactions']:.0f} interactions"
            )

        print(f"\n--- High Save Topics ---")
        for topic in insights.get("high_save_topics", [])[:5]:
            print(f"  - {topic}")

        print(f"\nRecommendation: {insights.get('recommendation', '')}")
    else:
        print(f"\n{insights.get('message', 'No insights available yet.')}")

    if args.json:
        print(
            f"\n--- JSON ---\n{json.dumps(insights, ensure_ascii=False, indent=2)}"
        )


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


def _print_results(
    results: list[dict], json_output: bool = False
) -> None:
    """Print content generation results."""
    for i, result in enumerate(results):
        success = result.get("pipeline_success", False)
        final = result.get("final_content")

        print(f"\n{'='*60}")
        print(
            f"Content {i+1}/{len(results)} - "
            f"{'SUCCESS' if success else 'FAILED'}"
        )
        print(f"{'='*60}")

        if final:
            print(f"Title: {final.title}")
            print(f"Quality: {final.quality_score:.2f}")
            print(f"Status: {final.status.value}")
            print(f"\n{final.body[:500]}...")
            if final.tags:
                print(f"\nTags: {' '.join(final.tags)}")

            # Show cover variants if available
            cover_variants = result.get("cover_variants", [])
            if cover_variants:
                print(f"\nCover variants: {len(cover_variants)}")
                for j, cv in enumerate(cover_variants):
                    print(
                        f"  [{j+1}] {cv.get('style', '?')}: "
                        f"\"{cv.get('text_overlay', '')}\" "
                        f"({cv.get('color_scheme', '')})"
                    )

            if final.feishu_doc_url:
                print(f"\nFeishu Doc: {final.feishu_doc_url}")

        if result.get("errors"):
            print(f"\nErrors: {result['errors']}")

    if json_output:
        output = []
        for r in results:
            final = r.get("final_content")
            if final:
                d = final.to_dict()
                d["cover_variants"] = r.get("cover_variants", [])
                output.append(d)
        print(
            f"\n--- JSON OUTPUT ---\n"
            f"{json.dumps(output, ensure_ascii=False, indent=2)}"
        )


def _print_matrix_status(manager: MatrixManager) -> None:
    """Print matrix account status."""
    print(f"\n{'='*60}")
    print("MATRIX ACCOUNT STATUS")
    print(f"{'='*60}")

    accounts = manager.state.accounts
    print(f"\nTotal accounts: {len(accounts)}")
    print(f"Active accounts: {len(manager.get_active_accounts())}")
    print(f"Daily output: {manager.get_total_daily_output()} pieces/day")
    print(f"Weekly output: {manager.get_total_daily_output() * 7} pieces/week")

    for account in accounts:
        stats = manager.get_account_stats(account.account_id)
        status = "ACTIVE" if account.active else "PAUSED"

        print(f"\n  [{status}] {account.name} ({account.account_id})")
        print(f"    Vertical: {account.vertical}")
        print(f"    Tone: {account.tone}")
        print(f"    Domains: {', '.join(account.domains)}")
        print(f"    Schedule: {account.daily_count}/day at {', '.join(account.posting_times[:account.daily_count])}")
        if stats["total"] > 0:
            print(
                f"    Stats: {stats['total']} generated, "
                f"{stats['passed']} approved ({stats['pass_rate']:.0%}), "
                f"avg quality {stats['avg_quality']:.2f}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="自媒体 AI 工作流 - 全自动矩阵号内容生产系统",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run: single account mode
    run_parser = subparsers.add_parser("run", help="单次内容生成")
    run_parser.add_argument("--topic", "-t", help="指定话题")
    run_parser.add_argument("--count", "-n", type=int, default=1, help="生成篇数")
    run_parser.add_argument("--json", action="store_true", help="输出JSON格式")
    run_parser.add_argument(
        "--dry-run", action="store_true", help="使用模拟数据测试"
    )

    # matrix: multi-account batch mode
    matrix_parser = subparsers.add_parser("matrix", help="矩阵号批量生成")
    matrix_parser.add_argument(
        "--account", "-a", help="指定账号ID（不指定则全部活跃账号）"
    )
    matrix_parser.add_argument("--count", "-n", type=int, help="每账号生成篇数（默认按账号配置）")
    matrix_parser.add_argument("--status", action="store_true", help="查看矩阵状态")
    matrix_parser.add_argument("--json", action="store_true", help="输出JSON格式")
    matrix_parser.add_argument(
        "--dry-run", action="store_true", help="使用模拟数据测试"
    )

    # analytics: performance tracking
    analytics_parser = subparsers.add_parser("analytics", help="数据分析与迭代优化")
    analytics_parser.add_argument(
        "--update", help="更新指定content_id的表现数据"
    )
    analytics_parser.add_argument("--likes", type=int, help="点赞数")
    analytics_parser.add_argument("--saves", type=int, help="收藏数")
    analytics_parser.add_argument("--comments", type=int, help="评论数")
    analytics_parser.add_argument("--shares", type=int, help="分享数")
    analytics_parser.add_argument("--views", type=int, help="浏览数")
    analytics_parser.add_argument("--json", action="store_true", help="输出JSON格式")

    # schedule: daily automation
    subparsers.add_parser("schedule", help="启动定时任务模式")

    args = parser.parse_args()
    config = AppConfig.from_env()

    is_dry_run = getattr(args, "dry_run", False)
    is_info_only = (
        (args.command == "matrix" and getattr(args, "status", False))
        or args.command == "analytics"
    )
    needs_api = args.command in ("run", "matrix", "schedule") and not is_info_only
    if needs_api and not config.ai.api_key and not is_dry_run:
        print(
            "Error: ANTHROPIC_API_KEY not set. "
            "See .env.example or use --dry-run."
        )
        sys.exit(1)

    commands = {
        "run": cmd_run,
        "matrix": cmd_matrix,
        "analytics": cmd_analytics,
        "schedule": cmd_schedule,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
