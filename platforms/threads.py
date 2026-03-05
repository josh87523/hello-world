"""Threads 平台适配器 — Playwright 自动化发布。"""

from __future__ import annotations

import logging
from typing import Any

from models.content import ContentFinal, Platform
from platforms.browser_base import BrowserPlatformAdapter

logger = logging.getLogger(__name__)

THREADS_MAX_LENGTH = 500


class ThreadsAdapter(BrowserPlatformAdapter):

    @property
    def platform(self) -> Platform:
        return Platform.THREADS

    def format_content(self, content: ContentFinal) -> dict[str, Any]:
        body = content.body
        if len(body) > THREADS_MAX_LENGTH:
            body = body[:THREADS_MAX_LENGTH - 1] + "…"

        return {
            "platform": "threads",
            "body": body,
            "images": content.image_urls[:10],
        }

    def validate_content(self, content: ContentFinal) -> list[str]:
        errors = []
        if not content.body:
            errors.append("内容不能为空")
        return errors

    async def _check_login(self, page) -> bool:
        await page.goto("https://www.threads.net/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(5000)

        # 点击 Create 按钮，看弹出的是编辑器还是登录提示
        try:
            create_btn = page.locator('[aria-label="Create"], [aria-label="创建"]').first
            await create_btn.click()
            await page.wait_for_timeout(2000)

            # 未登录：弹出"注册后可发布内容"
            login_prompt = await page.query_selector('text=注册后可发布内容')
            login_prompt2 = await page.query_selector('text=用 Instagram 登录')
            if login_prompt or login_prompt2:
                return False

            # 已登录：弹出编辑器（有 contenteditable 或 textbox）
            editor = await page.query_selector('[contenteditable="true"], [role="textbox"]')
            if editor:
                # 关闭 dialog 以免影响后续操作
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
                return True

            return False
        except Exception:
            return False

    async def _do_publish(self, page, formatted: dict[str, Any]) -> dict[str, Any]:
        body = formatted["body"]

        # 点击创建按钮
        create_btn = page.locator('[aria-label="Create"], [aria-label="创建"]').first
        await create_btn.click()
        await page.wait_for_timeout(2000)

        # 在编辑器中输入
        editor = page.locator('[contenteditable="true"]').first
        await editor.click()
        await page.wait_for_timeout(500)

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

        # 点击 Post/发布
        post_btn = page.locator('div[role="button"]:has-text("Post"), div[role="button"]:has-text("发布")').first
        await post_btn.click(force=True)
        await page.wait_for_timeout(3000)

        logger.info("Threads 帖子发布成功")
        return {"success": True, "url": "https://www.threads.net"}

    def get_platform_rules(self) -> dict[str, Any]:
        return {
            "body_max_length": THREADS_MAX_LENGTH,
            "max_images": 10,
            "tips": [
                "Threads 风格偏随性对话",
                "短内容表现更好",
            ],
        }
