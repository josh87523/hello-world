"""Instagram 平台适配器 — Playwright 自动化发布。"""

from __future__ import annotations

import logging
from typing import Any

from models.content import ContentFinal, Platform
from platforms.browser_base import BrowserPlatformAdapter

logger = logging.getLogger(__name__)

IG_CAPTION_MAX_LENGTH = 2200
IG_MAX_HASHTAGS = 30
IG_MAX_IMAGES = 10


class InstagramAdapter(BrowserPlatformAdapter):

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    def format_content(self, content: ContentFinal) -> dict[str, Any]:
        body = content.body
        # Instagram 喜欢大量 hashtags
        hashtags = [f"#{t.strip('#')}" for t in content.tags[:IG_MAX_HASHTAGS] if t.strip()]
        if hashtags:
            tag_block = "\n\n" + " ".join(hashtags)
            max_body = IG_CAPTION_MAX_LENGTH - len(tag_block)
            if len(body) > max_body:
                body = body[:max_body - 1] + "…"
            body = body + tag_block

        return {
            "platform": "instagram",
            "body": body,
            "images": content.image_urls[:IG_MAX_IMAGES],
        }

    def validate_content(self, content: ContentFinal) -> list[str]:
        errors = []
        if not content.body:
            errors.append("Caption 不能为空")
        if not content.image_urls:
            errors.append("Instagram 必须有图片")
        return errors

    async def _check_login(self, page) -> bool:
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)

        if "/accounts/login" in page.url:
            return False

        # 已登录：有创建帖子按钮
        try:
            await page.wait_for_selector('[aria-label="New post"], [aria-label="新帖子"]', timeout=5000)
            return True
        except Exception:
            return False

    async def _do_publish(self, page, formatted: dict[str, Any]) -> dict[str, Any]:
        body = formatted["body"]
        images = formatted.get("images", [])

        if not images:
            return {"success": False, "error": "Instagram 必须有图片"}

        # 点击创建帖子
        create_btn = page.locator('[aria-label="New post"], [aria-label="新帖子"]').first
        await create_btn.click()
        await page.wait_for_timeout(2000)

        # 上传图片
        file_input = page.locator('input[type="file"]').first
        await file_input.set_input_files(images[0])
        await page.wait_for_timeout(3000)

        # 如果有多张图片
        for img in images[1:]:
            try:
                add_more = page.locator('[aria-label="Open media gallery"]').first
                await add_more.click()
                await page.wait_for_timeout(1000)
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(img)
                await page.wait_for_timeout(2000)
            except Exception:
                break

        # 点 Next（跳过滤镜）
        for _ in range(2):
            try:
                next_btn = page.locator('div[role="button"]:has-text("Next"), button:has-text("Next"), button:has-text("下一步")').first
                await next_btn.click()
                await page.wait_for_timeout(2000)
            except Exception:
                break

        # 输入 caption
        caption_input = page.locator('[aria-label="Write a caption..."], [aria-label="写说明..."]').first
        await caption_input.click()
        await page.wait_for_timeout(500)

        lines = body.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=10)
            if i < len(lines) - 1:
                await page.keyboard.press("Enter")

        await page.wait_for_timeout(1000)

        # 分享
        share_btn = page.locator('div[role="button"]:has-text("Share"), button:has-text("Share"), button:has-text("分享")').first
        await share_btn.click()
        await page.wait_for_timeout(5000)

        logger.info("Instagram 帖子发布成功")
        return {"success": True, "url": "https://www.instagram.com"}

    def get_platform_rules(self) -> dict[str, Any]:
        return {
            "caption_max_length": IG_CAPTION_MAX_LENGTH,
            "max_hashtags": IG_MAX_HASHTAGS,
            "max_images": IG_MAX_IMAGES,
            "tips": [
                "Instagram 以视觉为主，图片质量最重要",
                "Hashtag 建议 15-25 个",
                "发布后快速互动有助于推荐",
            ],
        }
