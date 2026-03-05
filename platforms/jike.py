"""即刻平台适配器 — Playwright 自动化发布。"""

from __future__ import annotations

import logging
from typing import Any

from models.content import ContentFinal, Platform
from platforms.browser_base import BrowserPlatformAdapter

logger = logging.getLogger(__name__)

JIKE_MAX_LENGTH = 2000


class JikeAdapter(BrowserPlatformAdapter):

    @property
    def platform(self) -> Platform:
        return Platform.JIKE

    def format_content(self, content: ContentFinal) -> dict[str, Any]:
        body = content.body
        if len(body) > JIKE_MAX_LENGTH:
            body = body[:JIKE_MAX_LENGTH - 1] + "…"

        return {
            "platform": "jike",
            "body": body,
            "images": content.image_urls[:9],
        }

    def validate_content(self, content: ContentFinal) -> list[str]:
        errors = []
        if not content.body:
            errors.append("内容不能为空")
        return errors

    async def _check_login(self, page) -> bool:
        """导航到即刻检查登录状态。"""
        await page.goto("https://web.okjike.com/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)

        # 已登录会跳转到 /following 并显示头像
        if "/following" in page.url:
            return True

        try:
            await page.wait_for_selector('[class*="avatar"], [class*="Avatar"]', timeout=5000)
            return True
        except Exception:
            return False

    async def _do_publish(self, page, formatted: dict[str, Any]) -> dict[str, Any]:
        """在即刻发动态。"""
        body = formatted["body"]

        # 点击 "分享你的想法..." 输入区域
        compose = page.locator('textarea, [contenteditable="true"], [placeholder*="想法"]').first
        await compose.click()
        await page.wait_for_timeout(1000)

        # 输入内容
        lines = body.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=15)
            if i < len(lines) - 1:
                await page.keyboard.press("Enter")

        await page.wait_for_timeout(1000)

        # 图片上传
        images = formatted.get("images", [])
        if images:
            file_input = page.locator('input[type="file"]').first
            for img_path in images:
                await file_input.set_input_files(img_path)
                await page.wait_for_timeout(2000)

        # 点击发送（即刻用"发送"不是"发布"）
        submit = page.locator('button:has-text("发送"), button:has-text("发布")').first
        await submit.click()
        await page.wait_for_timeout(3000)

        logger.info("即刻动态发布成功")
        return {"success": True, "url": "https://web.okjike.com"}

    def get_platform_rules(self) -> dict[str, Any]:
        return {
            "body_max_length": JIKE_MAX_LENGTH,
            "max_images": 9,
            "tips": [
                "即刻偏科技/互联网圈，观点输出效果好",
                "带图帖子互动更高",
            ],
        }
