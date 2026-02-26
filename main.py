"""Social Media AI Workflow - Main entry point.

自媒体 AI 工作流：从选题到发布的全自动化内容生产系统。
支持矩阵号运营、对标分析、数据爬取、封面策略与迭代优化。

Usage:
    # 单次生成
    python main.py run

    # 指定话题
    python main.py run --topic "AI Agent 正在替代程序员？"

    # 矩阵批量生成
    python main.py matrix
    python main.py matrix --account matrix_01
    python main.py matrix --status

    # 数据爬取
    python main.py scrape --keyword "AI工具推荐" --count 30
    python main.py scrape --user <user_id> --count 50
    python main.py scrape --note <note_id>
    python main.py scrape --import data/notes.json

    # 对标分析
    python main.py benchmark --add <user_id> --name "博主昵称" --vertical ai_tools
    python main.py benchmark --list
    python main.py benchmark --analyze
    python main.py benchmark --report

    # 数据分析
    python main.py analytics
    python main.py analytics --update <id> --likes 500 --saves 300

    # 定时任务
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
from modules.competitor_analyzer import CompetitorAnalyzer
from modules.matrix_manager import MatrixManager
from modules.xhs_scraper import ScraperConfig as XhsScraperConfig, XhsScraper

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


def cmd_scrape(args: argparse.Namespace, config: AppConfig) -> None:
    """Scrape data from Xiaohongshu."""
    scraper_cfg = XhsScraperConfig(
        cookie=config.scraper.cookie,
        rate_limit=config.scraper.rate_limit,
        max_notes_per_search=config.scraper.max_notes_per_search,
        max_notes_per_user=config.scraper.max_notes_per_user,
        data_dir=config.scraper.data_dir,
    )

    # Import from file (no cookie needed)
    if args.import_file:
        scraper = XhsScraper(scraper_cfg)
        notes = scraper.import_from_file(args.import_file)
        if notes:
            print(f"Imported {len(notes)} notes from {args.import_file}")
            _print_scraped_notes(notes, top_n=args.top or 10, json_output=args.json)
        else:
            print("No notes imported. Check file format.")
        return

    # Online scraping requires cookie
    if not scraper_cfg.is_configured:
        print(
            "Error: XHS_COOKIE not set. Required for online scraping.\n"
            "Set XHS_COOKIE in .env or use --import to load from file."
        )
        sys.exit(1)

    scraper = XhsScraper(scraper_cfg)

    if args.keyword:
        notes = scraper.search_notes(
            args.keyword,
            count=args.count or scraper_cfg.max_notes_per_search,
        )
        print(f"\nSearch results for '{args.keyword}': {len(notes)} notes")
        _print_scraped_notes(notes, top_n=args.top or 10, json_output=args.json)

    elif args.user:
        notes = scraper.scrape_user_notes(
            args.user,
            count=args.count or scraper_cfg.max_notes_per_user,
        )
        print(f"\nUser {args.user}: {len(notes)} notes scraped")
        _print_scraped_notes(notes, top_n=args.top or 10, json_output=args.json)

    elif args.note:
        note = scraper.scrape_note_detail(args.note)
        if note:
            print(f"\nNote detail: {note.note_id}")
            print(f"Title: {note.title}")
            print(f"Author: {note.author_name}")
            print(f"Likes: {note.likes} | Saves: {note.saves} | Comments: {note.comments}")
            print(f"Save/Like ratio: {note.save_like_ratio:.2f}")
            print(f"Tags: {', '.join(note.tags)}")
            print(f"\n{note.body[:1000]}")
            if args.json:
                print(f"\n--- JSON ---\n{json.dumps(note.to_dict(), ensure_ascii=False, indent=2)}")
        else:
            print(f"Failed to scrape note: {args.note}")
    else:
        print("Specify --keyword, --user, --note, or --import. See --help.")

    scraper.close()


def cmd_benchmark(args: argparse.Namespace, config: AppConfig) -> None:
    """Manage competitor benchmarks and analysis."""
    # Build AI client for analysis (optional)
    ai_client = None
    has_api = bool(config.ai.api_key)
    if has_api:
        ai_client = AIClient(api_key=config.ai.api_key, model=config.ai.model)

    # Build scraper (optional, for online scraping)
    scraper = None
    if config.scraper.is_configured:
        scraper_cfg = XhsScraperConfig(
            cookie=config.scraper.cookie,
            rate_limit=config.scraper.rate_limit,
            data_dir=config.scraper.data_dir,
        )
        scraper = XhsScraper(scraper_cfg)

    analyzer = CompetitorAnalyzer(
        ai=ai_client,
        scraper=scraper,
        data_file=config.scraper.benchmark_file,
    )

    if args.add:
        comp = analyzer.add_competitor(
            user_id=args.add,
            nickname=args.name or args.add,
            vertical=args.vertical or "",
        )
        print(f"Added competitor: {comp.nickname} ({comp.user_id})")

        # Auto-scrape if cookie available
        if scraper:
            print(f"Scraping {comp.nickname}'s notes...")
            notes = analyzer.scrape_competitor(comp.user_id, count=args.count or 30)
            print(f"Scraped {len(notes)} notes")
            analyzer.compute_competitor_stats(comp.user_id)
            _print_competitor(comp)

    elif args.remove:
        if analyzer.remove_competitor(args.remove):
            print(f"Removed competitor: {args.remove}")
        else:
            print(f"Competitor not found: {args.remove}")

    elif args.list:
        competitors = analyzer.list_competitors()
        if not competitors:
            print("No competitors tracked. Use --add <user_id> to add one.")
            return

        print(f"\n{'='*60}")
        print(f"BENCHMARK ACCOUNTS ({len(competitors)})")
        print(f"{'='*60}")

        for comp in competitors:
            _print_competitor(comp)

    elif args.analyze:
        if args.analyze == "all":
            # Scrape and analyze all
            if scraper:
                print("Scraping all competitors...")
                total = analyzer.scrape_all_competitors(count=args.count or 30)
                print(f"Total notes scraped: {total}")

            analyzer.compute_all_stats()

            # AI analysis per competitor
            if ai_client:
                for comp in analyzer.competitors:
                    print(f"\nAnalyzing {comp.nickname}...")
                    style = analyzer.analyze_competitor_style(comp.user_id)
                    if style:
                        print(f"  Style: {style.get('writing_style', 'N/A')[:100]}")
                        print(f"  Strategies: {', '.join(style.get('reusable_strategies', []))}")

            print("\nAnalysis complete.")
            for comp in analyzer.competitors:
                _print_competitor(comp)
        else:
            # Analyze specific competitor
            user_id = args.analyze
            if scraper:
                analyzer.scrape_competitor(user_id, count=args.count or 30)
            comp = analyzer.compute_competitor_stats(user_id)
            if comp:
                _print_competitor(comp)
                if ai_client:
                    style = analyzer.analyze_competitor_style(user_id)
                    if style:
                        print(f"\n  Content style analysis:")
                        print(f"    Style: {style.get('writing_style', 'N/A')}")
                        print(f"    Structure: {style.get('content_structure', 'N/A')}")
                        for s in style.get("reusable_strategies", []):
                            print(f"    Strategy: {s}")
            else:
                print(f"Competitor not found: {user_id}")

    elif args.report:
        if not analyzer.competitors:
            print("No competitors to report on. Use --add first.")
            return

        print("Generating benchmark report...")
        report = analyzer.generate_report()

        print(f"\n{'='*60}")
        print("BENCHMARK REPORT")
        print(f"{'='*60}")

        print(f"\nCompetitors analyzed: {len(report.competitors)}")
        print(f"Total notes: {sum(c.total_notes for c in report.competitors)}")
        print(f"Avg save/like ratio: {report.avg_save_like_ratio:.2f}")

        if report.title_patterns:
            print(f"\n--- Title patterns ---")
            for p in report.title_patterns:
                print(f"  - {p}")

        if report.content_patterns:
            print(f"\n--- Viral traits ---")
            for p in report.content_patterns:
                print(f"  - {p}")

        if report.best_tags:
            print(f"\n--- Best tags ---")
            print(f"  {', '.join(report.best_tags[:15])}")

        if report.recommendations:
            print(f"\n--- Action items ---")
            for r in report.recommendations:
                print(f"  - {r}")

        if args.json:
            print(f"\n--- JSON ---\n{json.dumps(report.to_dict(), ensure_ascii=False, indent=2)}")

    elif args.insights:
        insights = analyzer.get_topic_insights()
        if not insights.get("has_benchmark"):
            print("No benchmark data. Use --add and --analyze first.")
            return

        print(f"\n{'='*60}")
        print("COMPETITOR INSIGHTS FOR TOPIC RESEARCH")
        print(f"{'='*60}")
        print(f"\nCompetitors: {insights['competitor_count']}")
        print(f"Notes analyzed: {insights['total_notes_analyzed']}")
        print(f"Avg viral rate: {insights['avg_viral_rate']:.1%}")

        print(f"\n--- Top performing titles ---")
        for t in insights.get("top_performing_titles", [])[:10]:
            print(f"  [{t['interactions']}] {t['title']}")

        print(f"\n--- Best tags ---")
        print(f"  {', '.join(insights.get('best_tags', []))}")

    else:
        print("Specify --add, --list, --analyze, --report, or --insights. See --help.")

    if scraper:
        scraper.close()


def _print_scraped_notes(
    notes: list, top_n: int = 10, json_output: bool = False
) -> None:
    """Print scraped notes summary."""
    sorted_notes = sorted(notes, key=lambda n: n.total_interactions, reverse=True)

    print(f"\n--- Top {min(top_n, len(sorted_notes))} by engagement ---")
    for i, n in enumerate(sorted_notes[:top_n]):
        print(
            f"  {i+1}. [{n.total_interactions}互动] {n.title}\n"
            f"     赞{n.likes} 藏{n.saves} 评{n.comments} "
            f"| 藏赞比{n.save_like_ratio:.2f} "
            f"| @{n.author_name}"
        )

    # Summary stats
    if notes:
        avg_likes = sum(n.likes for n in notes) / len(notes)
        avg_saves = sum(n.saves for n in notes) / len(notes)
        total_saves = sum(n.saves for n in notes)
        total_likes = sum(n.likes for n in notes)
        viral = sum(1 for n in notes if n.total_interactions >= 1000)
        print(f"\n  Summary: {len(notes)} notes, avg {avg_likes:.0f} likes, "
              f"avg {avg_saves:.0f} saves, "
              f"save/like {total_saves/total_likes:.2f}" if total_likes else "",
              f", viral {viral}/{len(notes)} ({viral/len(notes):.0%})")

    if json_output:
        print(f"\n--- JSON ---\n{json.dumps([n.to_dict() for n in sorted_notes[:top_n]], ensure_ascii=False, indent=2)}")


def _print_competitor(comp) -> None:
    """Print a single competitor's stats."""
    print(f"\n  {comp.nickname} ({comp.user_id})")
    print(f"    Vertical: {comp.vertical or 'N/A'}")
    print(f"    Notes: {comp.total_notes} | Followers: {comp.followers:,}")
    if comp.avg_likes > 0:
        print(
            f"    Avg likes: {comp.avg_likes:.0f} | "
            f"Avg saves: {comp.avg_saves:.0f} | "
            f"Save/like: {comp.avg_save_like_ratio:.2f}"
        )
        print(f"    Viral rate: {comp.viral_rate:.1%}")
    if comp.posting_frequency:
        print(f"    Posting: {comp.posting_frequency}")
    if comp.common_tags:
        print(f"    Top tags: {', '.join(comp.common_tags[:8])}")
    if comp.last_scraped:
        print(f"    Last scraped: {comp.last_scraped[:19]}")


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

    # scrape: data scraping
    scrape_parser = subparsers.add_parser("scrape", help="小红书数据爬取")
    scrape_parser.add_argument("--keyword", "-k", help="按关键词搜索笔记")
    scrape_parser.add_argument("--user", "-u", help="爬取指定用户的笔记")
    scrape_parser.add_argument("--note", help="爬取单条笔记详情")
    scrape_parser.add_argument("--import", dest="import_file", help="从JSON文件导入笔记数据")
    scrape_parser.add_argument("--count", "-n", type=int, help="最大爬取数量")
    scrape_parser.add_argument("--top", type=int, help="显示前N条结果")
    scrape_parser.add_argument("--json", action="store_true", help="输出JSON格式")

    # benchmark: competitor analysis
    bench_parser = subparsers.add_parser("benchmark", help="对标账号分析")
    bench_parser.add_argument("--add", help="添加对标账号（传入user_id）")
    bench_parser.add_argument("--name", help="对标账号昵称（配合--add使用）")
    bench_parser.add_argument("--vertical", help="对标账号垂类（配合--add使用）")
    bench_parser.add_argument("--remove", help="移除对标账号（传入user_id）")
    bench_parser.add_argument("--list", action="store_true", help="列出所有对标账号")
    bench_parser.add_argument("--analyze", nargs="?", const="all", help="分析对标账号（指定user_id或all）")
    bench_parser.add_argument("--report", action="store_true", help="生成对标分析报告")
    bench_parser.add_argument("--insights", action="store_true", help="查看对标洞察（供选题参考）")
    bench_parser.add_argument("--count", "-n", type=int, help="爬取笔记数量")
    bench_parser.add_argument("--json", action="store_true", help="输出JSON格式")

    # schedule: daily automation
    subparsers.add_parser("schedule", help="启动定时任务模式")

    args = parser.parse_args()
    config = AppConfig.from_env()

    is_dry_run = getattr(args, "dry_run", False)
    is_info_only = (
        (args.command == "matrix" and getattr(args, "status", False))
        or args.command == "analytics"
        or args.command == "scrape"
        or args.command == "benchmark"
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
        "scrape": cmd_scrape,
        "benchmark": cmd_benchmark,
        "schedule": cmd_schedule,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
