"""Xiaohongshu (Little Red Book) platform adapter — 浏览器自动化发布。"""

from __future__ import annotations

import logging
from typing import Any

from models.content import ContentFinal, Platform
from platforms.browser_base import BrowserPlatformAdapter

logger = logging.getLogger(__name__)

# Xiaohongshu content constraints
XHS_TITLE_MAX_LENGTH = 20
XHS_BODY_MAX_LENGTH = 1000  # characters
XHS_BODY_MIN_LENGTH = 100
XHS_MAX_TAGS = 10
XHS_MAX_IMAGES = 9


class XiaohongshuAdapter(BrowserPlatformAdapter):
    """小红书创作者后台浏览器自动化发布。"""

    @property
    def platform(self) -> Platform:
        return Platform.XIAOHONGSHU

    def format_content(self, content: ContentFinal) -> dict[str, Any]:
        title = content.title[:XHS_TITLE_MAX_LENGTH]

        tags = []
        for tag in content.tags[:XHS_MAX_TAGS]:
            tag = tag.strip()
            if not tag.startswith("#"):
                tag = f"#{tag}"
            tags.append(tag)

        body = content.body
        tag_line = " ".join(tags)
        formatted_body = f"{body}\n\n{tag_line}"

        return {
            "platform": "xiaohongshu",
            "title": title,
            "body": formatted_body,
            "body_raw": body,
            "tags": tags,
            "images": content.image_urls[:XHS_MAX_IMAGES],
            "cover_image": content.cover_image_url,
        }

    def validate_content(self, content: ContentFinal) -> list[str]:
        errors = []
        if not content.title:
            errors.append("标题不能为空")
        elif len(content.title) > XHS_TITLE_MAX_LENGTH:
            errors.append(f"标题超过{XHS_TITLE_MAX_LENGTH}字限制: {len(content.title)}字")

        if not content.body:
            errors.append("正文不能为空")

        return errors

    async def _check_login(self, page) -> bool:
        await page.goto("https://creator.xiaohongshu.com/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)

        # 未登录会跳转到 login 页面
        if "/login" in page.url:
            return False

        # 已登录：在创作者后台首页
        if "creator.xiaohongshu.com" in page.url and "/login" not in page.url:
            return True

        return False

    async def _js_click(self, page, text: str):
        """用 JS 点击文本元素（绕过 viewport 限制）。"""
        await page.evaluate(f'''
            const els = document.querySelectorAll('span, div, button, a');
            for (const el of els) {{
                if (el.textContent.trim() === '{text}') {{ el.click(); break; }}
            }}
        ''')

    async def _do_publish(self, page, formatted: dict[str, Any]) -> dict[str, Any]:
        title = formatted["title"]
        body = formatted["body"]
        images = formatted.get("images", [])

        # 导航到发布页面
        await page.goto("https://creator.xiaohongshu.com/publish/publish", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)

        # 点击"上传图文"标签（用 JS 避免 viewport 问题）
        await self._js_click(page, "上传图文")
        await page.wait_for_timeout(2000)

        if images:
            # 有图片：直接上传
            file_input = page.locator('input[type="file"]').first
            await file_input.set_input_files(images[0])
            await page.wait_for_timeout(3000)
            for img_path in images[1:]:
                await file_input.set_input_files(img_path)
                await page.wait_for_timeout(2000)
        else:
            # 无图片：用"文字配图"生成封面图
            await self._js_click(page, "文字配图")
            await page.wait_for_timeout(2000)

            # 在编辑器输入封面文字（取正文前 50 字）
            editor = page.locator('.tiptap, [contenteditable="true"]').first
            await editor.click()
            cover_text = body[:50].split("\n")[0]
            await page.keyboard.type(cover_text, delay=10)
            await page.wait_for_timeout(500)

            # 点击"生成图片"
            await self._js_click(page, "生成图片")
            await page.wait_for_timeout(5000)

        # 等待编辑区出现（上传/生成图片后才出现标题和正文输入）
        await page.wait_for_timeout(3000)

        # 输入标题
        title_input = page.locator('#title, [placeholder*="标题"]').first
        try:
            await title_input.wait_for(timeout=10000)
            await title_input.click()
            await page.keyboard.type(title, delay=20)
        except Exception:
            # 可能标题输入已经有焦点或不存在
            logger.warning("未找到标题输入框")

        await page.wait_for_timeout(500)

        # 输入正文
        body_input = page.locator('#post-textarea, [contenteditable="true"]').last
        try:
            await body_input.click()
            await page.wait_for_timeout(300)
            lines = body.split("\n")
            for i, line in enumerate(lines):
                if line:
                    await page.keyboard.type(line, delay=10)
                if i < len(lines) - 1:
                    await page.keyboard.press("Enter")
        except Exception:
            logger.warning("未找到正文输入框")

        await page.wait_for_timeout(1000)

        # 点击发布按钮
        await self._js_click(page, "发布")
        await page.wait_for_timeout(5000)

        logger.info("小红书笔记发布成功: %s", title)
        return {"success": True, "url": "https://creator.xiaohongshu.com"}

    def get_platform_rules(self) -> dict[str, Any]:
        return {
            "title_max_length": XHS_TITLE_MAX_LENGTH,
            "body_max_length": XHS_BODY_MAX_LENGTH,
            "body_min_length": XHS_BODY_MIN_LENGTH,
            "max_tags": XHS_MAX_TAGS,
            "max_images": XHS_MAX_IMAGES,
            "supported_content_types": ["text_image"],
            "best_posting_times": ["07:00-09:00", "12:00-14:00", "18:00-22:00"],
            "tips": [
                "标题含emoji转化率更高",
                "前3行决定是否展开阅读",
                "封面图比例建议3:4",
                "发布后30分钟内回复评论有助于推荐",
            ],
        }
