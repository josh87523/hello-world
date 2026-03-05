"""多平台发布编排器。

接收各平台已适配的内容，校验后顺序发布，收集结果。

用法：
    publisher = MultiPlatformPublisher()
    results = await publisher.publish_all(contents)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from models.content import ContentFinal, ContentDraft, ContentIdea, ContentType, Platform, ContentStatus
from platforms.registry import PlatformRegistry


PROFILES_DIR = Path(__file__).parent.parent / "profiles"


@dataclass
class PublishResult:
    platform: str
    success: bool
    url: str = ""
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def build_content_final(platform: Platform, data: dict[str, Any]) -> ContentFinal:
    """从 dict 构建 ContentFinal 对象。

    data 格式：
    {
        "title": "标题",
        "body": "正文",
        "tags": ["tag1", "tag2"],
        "images": ["path/to/img1.png"]  # 可选
    }
    """
    idea = ContentIdea(topic=data.get("title", ""), angle="multi-platform publish")
    draft = ContentDraft(idea=idea, platform=platform, content_type=ContentType.TEXT_IMAGE)
    return ContentFinal(
        draft=draft,
        title=data.get("title", ""),
        body=data.get("body", ""),
        tags=data.get("tags", []),
        image_urls=data.get("images", []),
        platform=platform,
        status=ContentStatus.APPROVED,
    )


class MultiPlatformPublisher:
    """多平台发布编排。"""

    def __init__(self):
        self.registry = PlatformRegistry

    def publish_all(
        self,
        contents: dict[str, dict[str, Any]],
        dry_run: bool = False,
    ) -> list[PublishResult]:
        """发布到多个平台。

        Args:
            contents: {platform_name: {title, body, tags, images}}
            dry_run: 只校验不发布
        """
        results = []

        for platform_name, data in contents.items():
            try:
                platform = Platform(platform_name)
            except ValueError:
                results.append(PublishResult(
                    platform=platform_name, success=False,
                    error=f"未知平台: {platform_name}",
                ))
                continue

            try:
                adapter = self.registry.get(platform)
            except ValueError as e:
                results.append(PublishResult(
                    platform=platform_name, success=False,
                    error=str(e),
                ))
                continue

            content = build_content_final(platform, data)

            # 校验
            errors = adapter.validate_content(content)
            if errors:
                results.append(PublishResult(
                    platform=platform_name, success=False,
                    error=f"校验失败: {'; '.join(errors)}",
                ))
                continue

            if dry_run:
                formatted = adapter.format_content(content)
                results.append(PublishResult(
                    platform=platform_name, success=True,
                    details={"formatted": formatted, "dry_run": True},
                ))
                print(f"  [dry-run] {platform_name}: 校验通过")
                continue

            # 发布
            try:
                result = adapter.publish(content)
                results.append(PublishResult(
                    platform=platform_name,
                    success=result.get("success", False),
                    url=result.get("url", ""),
                    error=result.get("error", ""),
                    details=result,
                ))
            except Exception as e:
                results.append(PublishResult(
                    platform=platform_name, success=False,
                    error=str(e),
                ))

        return results

    @staticmethod
    def print_results(results: list[PublishResult]) -> None:
        """打印发布结果。"""
        print(f"\n{'='*50}")
        print("发布结果")
        print(f"{'='*50}")

        for r in results:
            status = "✓" if r.success else "✗"
            print(f"  {status} {r.platform}", end="")
            if r.url:
                print(f" → {r.url}")
            elif r.error:
                print(f" — {r.error}")
            elif r.details.get("dry_run"):
                print(f" (dry-run 通过)")
            else:
                print()

        success = sum(1 for r in results if r.success)
        print(f"\n  {success}/{len(results)} 成功")


def load_content_json(filepath: str) -> dict[str, dict[str, Any]]:
    """从 JSON 文件加载多平台内容。"""
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)
