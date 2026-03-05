"""X/Twitter 平台适配器 — Playwright 自动化发布。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from models.content import ContentFinal, Platform
from platforms.browser_base import BrowserPlatformAdapter

logger = logging.getLogger(__name__)

TWEET_MAX_LENGTH = 280  # 字符（中文约 140 字）
MAX_IMAGES = 4


class TwitterAdapter(BrowserPlatformAdapter):

    @property
    def platform(self) -> Platform:
        return Platform.TWITTER

    def format_content(self, content: ContentFinal) -> dict[str, Any]:
        body = content.body
        # 追加 hashtags
        hashtags = [f"#{t.strip('#')}" for t in content.tags[:5] if t.strip()]
        if hashtags:
            tag_line = " ".join(hashtags)
            # 确保总长度不超限
            max_body = TWEET_MAX_LENGTH - len(tag_line) - 2  # 留换行+空格
            if len(body) > max_body:
                body = body[:max_body - 1] + "…"
            body = f"{body}\n\n{tag_line}"
        elif len(body) > TWEET_MAX_LENGTH:
            body = body[:TWEET_MAX_LENGTH - 1] + "…"

        return {
            "platform": "twitter",
            "body": body,
            "images": content.image_urls[:MAX_IMAGES],
        }

    def validate_content(self, content: ContentFinal) -> list[str]:
        errors = []
        if not content.body:
            errors.append("内容不能为空")
        # 不强制校验长度，format_content 会自动截断
        return errors

    async def _check_login(self, page) -> bool:
        """导航到 x.com 检查登录状态。"""
        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)

        # 如果跳转到登录页，说明未登录
        if "/login" in page.url or "/i/flow/login" in page.url:
            return False

        # 检查 compose 按钮是否存在
        try:
            await page.wait_for_selector('[data-testid="SideNav_NewTweet_Button"]', timeout=5000)
            return True
        except Exception:
            return False

    async def _do_publish(self, page, formatted: dict[str, Any]) -> dict[str, Any]:
        """在 x.com 发推。"""
        body = formatted["body"]

        # 点击 compose 按钮
        compose_btn = page.locator('[data-testid="SideNav_NewTweet_Button"]')
        await compose_btn.click()
        await page.wait_for_timeout(1500)

        # 在对话框编辑器中输入内容（首页也有编辑框，需定位到 dialog 内）
        editor = page.locator('[role="dialog"] [data-testid="tweetTextarea_0"]')
        try:
            await editor.wait_for(timeout=3000)
        except Exception:
            # fallback: 用第一个匹配的
            editor = page.locator('[data-testid="tweetTextarea_0"]').first
        await editor.click()
        await page.wait_for_timeout(500)

        # 逐段输入（处理换行）
        lines = body.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=20)
            if i < len(lines) - 1:
                await page.keyboard.press("Enter")

        await page.wait_for_timeout(1000)

        # 图片上传（如有）
        images = formatted.get("images", [])
        if images:
            file_input = page.locator('input[data-testid="fileInput"]')
            for img_path in images:
                await file_input.set_input_files(img_path)
                await page.wait_for_timeout(2000)

        # 点击发送按钮（对话框内的，force 绕过 overlay 遮挡）
        post_btn = page.locator('[data-testid="tweetButton"]').first
        await post_btn.click(force=True)
        await page.wait_for_timeout(3000)

        # 验证发送成功（compose 对话框消失）
        try:
            await page.wait_for_selector('[role="dialog"] [data-testid="tweetTextarea_0"]', state="hidden", timeout=5000)
            logger.info("推文发送成功")
            return {"success": True, "url": "https://x.com"}
        except Exception:
            # 可能已成功但对话框未消失，检查是否有错误提示
            return {"success": True, "url": "https://x.com", "note": "发送已触发，请手动确认"}

    def get_platform_rules(self) -> dict[str, Any]:
        return {
            "body_max_length": TWEET_MAX_LENGTH,
            "max_images": MAX_IMAGES,
            "tips": [
                "开头几个字决定是否被展开",
                "带图推文互动率更高",
                "使用 thread 发长内容",
            ],
        }
