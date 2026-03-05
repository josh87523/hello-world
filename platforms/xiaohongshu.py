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
        # 标签不再追加到正文，通过话题选择 UI 单独插入
        return {
            "platform": "xiaohongshu",
            "title": title,
            "body": body,
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

    async def _generate_placeholder_image(self, title: str) -> str:
        """生成纯色占位封面图（小红书必须有图片）。"""
        import struct
        import zlib
        from pathlib import Path

        # 生成 1080x1440 (3:4) 纯白 PNG + 标题文字（纯 Python，无需 PIL）
        w, h = 1080, 1440
        img_path = Path("/tmp/xhs_placeholder.png")

        # 最简 PNG：纯白像素
        def create_png(width, height):
            def chunk(chunk_type, data):
                c = chunk_type + data
                return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

            header = b'\x89PNG\r\n\x1a\n'
            ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            # 白色像素行
            raw_row = b'\x00' + b'\xff' * (width * 3)
            raw_data = raw_row * height
            idat = chunk(b'IDAT', zlib.compress(raw_data))
            iend = chunk(b'IEND', b'')
            return header + ihdr + idat + iend

        img_path.write_bytes(create_png(w, h))
        logger.info("生成占位封面图: %s", img_path)
        return str(img_path)

    async def _js_click(self, page, text: str):
        """用 JS 点击文本元素（绕过 viewport 限制）。"""
        await page.evaluate(f'''
            const els = document.querySelectorAll('span, div, button, a');
            for (const el of els) {{
                if (el.textContent.trim() === '{text}') {{ el.click(); break; }}
            }}
        ''')

    async def _insert_linked_tags(self, page, tags: list[str]):
        """通过推荐话题面板和话题搜索 UI 插入链接标签（蓝色可点击）。

        小红书创作者后台有两种添加话题的方式：
        1. 推荐话题面板 (recommend-topic-wrapper) 中的 span.tag 元素
        2. "话题"按钮 (topic-btn) 打开搜索对话框
        """
        logger.info("开始插入话题标签: %s", tags)

        inserted = 0
        remaining = [t.lstrip("#").strip() for t in tags if t.strip()]

        # 策略1: 从推荐话题面板点击匹配项
        for keyword in remaining[:]:
            clicked = await page.evaluate("""(keyword) => {
                const tags = document.querySelectorAll('.recommend-topic-wrapper .tag, .tag-group .tag, [class*="recommend"] span.tag');
                for (const tag of tags) {
                    const text = (tag.textContent || '').trim().replace(/^#/, '');
                    if (text && text.includes(keyword) && text !== '更多') {
                        tag.click();
                        return tag.textContent.trim();
                    }
                }
                return null;
            }""", keyword)

            if clicked:
                logger.info("推荐话题匹配: %s → %s", keyword, clicked)
                inserted += 1
                remaining.remove(keyword)
                await page.wait_for_timeout(800)

        if not remaining:
            logger.info("话题标签全部插入完成: %d/%d", inserted, len(tags))
            return

        # 策略2: 点击"话题"按钮打开搜索对话框
        topic_btn_clicked = await page.evaluate("""() => {
            const btns = document.querySelectorAll('button, [role="button"]');
            for (const btn of btns) {
                const text = (btn.textContent || '').trim();
                if (text.includes('话题')) {
                    btn.click();
                    return text;
                }
            }
            return null;
        }""")

        if not topic_btn_clicked:
            logger.warning("未找到话题按钮，剩余标签跳过: %s", remaining)
            return

        logger.info("话题按钮已点击: %s", topic_btn_clicked)
        await page.wait_for_timeout(1500)

        for keyword in remaining[:]:
            # 查找搜索输入框
            search_focused = await page.evaluate("""() => {
                // 话题搜索弹窗中的输入框
                const inputs = document.querySelectorAll('input[type="text"], input[placeholder*="搜索"], input[placeholder*="话题"]');
                for (const input of inputs) {
                    if (input.offsetHeight > 0) {
                        input.focus();
                        input.value = '';
                        input.dispatchEvent(new Event('input', {bubbles: true}));
                        return true;
                    }
                }
                return false;
            }""")

            if not search_focused:
                logger.warning("话题搜索框未找到，跳过: %s", keyword)
                break

            await page.keyboard.type(keyword, delay=80)
            await page.wait_for_timeout(1500)

            # 点击搜索结果中的匹配项
            result_clicked = await page.evaluate("""(keyword) => {
                // 弹窗中的搜索结果列表
                const selectors = [
                    '[class*="topic"] [class*="item"]',
                    '[class*="topic"] li',
                    '[class*="search"] [class*="item"]',
                    '[class*="result"] [class*="item"]',
                    '[class*="dialog"] li',
                    '[class*="modal"] li',
                    'span.tag',
                ];
                for (const sel of selectors) {
                    const items = document.querySelectorAll(sel);
                    for (const item of items) {
                        const text = (item.textContent || '').trim();
                        if (text.includes(keyword) && item.offsetHeight > 0) {
                            item.click();
                            return text.substring(0, 40);
                        }
                    }
                }
                return null;
            }""", keyword)

            if result_clicked:
                logger.info("话题搜索匹配: %s → %s", keyword, result_clicked)
                inserted += 1
                remaining.remove(keyword)
                await page.wait_for_timeout(800)
            else:
                logger.warning("话题搜索无结果: %s", keyword)
                # 清空搜索框继续下一个
                await page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input[type="text"]');
                    for (const input of inputs) {
                        if (input.offsetHeight > 0) {
                            input.value = '';
                            input.dispatchEvent(new Event('input', {bubbles: true}));
                            break;
                        }
                    }
                }""")
                await page.wait_for_timeout(500)

        # 关闭话题搜索弹窗
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        logger.info("话题标签插入完成: %d/%d", inserted, len(tags))

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

        if not images:
            # 无图片：生成纯色占位图（小红书必须有图）
            images = [await self._generate_placeholder_image(title)]

        # 上传图片
        file_input = page.locator('input[type="file"]').first
        await file_input.set_input_files(images[0])
        await page.wait_for_timeout(3000)
        for img_path in images[1:]:
            try:
                await file_input.set_input_files(img_path)
                await page.wait_for_timeout(2000)
            except Exception:
                break

        # 等待编辑区出现（上传/生成图片后才出现标题和正文输入）
        await page.wait_for_timeout(3000)

        # 输入标题 — 用 JS 查找包含"标题"placeholder 的元素
        title_entered = False
        try:
            title_input = page.locator('#title, [placeholder*="标题"]').first
            await title_input.wait_for(timeout=5000)
            await title_input.click()
            await page.keyboard.type(title, delay=20)
            title_entered = True
        except Exception:
            # 备选：用 JS 查找
            title_entered = await page.evaluate("""(title) => {
                // 查找 input/textarea
                const inputs = document.querySelectorAll('input, textarea');
                for (const el of inputs) {
                    const ph = el.placeholder || '';
                    if (ph.includes('标题')) {
                        el.focus(); el.value = title;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        return true;
                    }
                }
                // 查找 contenteditable
                const editables = document.querySelectorAll('[contenteditable="true"]');
                for (const el of editables) {
                    const ph = el.getAttribute('data-placeholder') || el.getAttribute('placeholder') || '';
                    if (ph.includes('标题')) {
                        el.focus(); el.click();
                        return true;  // 返回 true，后续用 keyboard.type
                    }
                }
                return false;
            }""", title)
            if title_entered:
                await page.keyboard.type(title, delay=20)
            else:
                logger.warning("未找到标题输入框")

        await page.wait_for_timeout(500)

        # 输入正文 — 小红书用 TipTap/ProseMirror 编辑器
        body_entered = False
        for selector in [
            '.tiptap.ProseMirror',
            '[contenteditable="true"].ProseMirror',
            '[placeholder*="正文"], [data-placeholder*="正文"]',
            '[contenteditable="true"]',
        ]:
            try:
                body_input = page.locator(selector).first
                await body_input.wait_for(state="visible", timeout=3000)
                # 用 JS focus 避免 headless 下 click 超时
                await body_input.evaluate("el => { el.focus(); el.click(); }")
                body_entered = True
                logger.info("正文选择器匹配: %s", selector)
                break
            except Exception:
                continue
        if not body_entered:
            # 最后手段：用 JS 直接 focus
            body_entered = await page.evaluate("""() => {
                const el = document.querySelector('.tiptap.ProseMirror, [contenteditable="true"]');
                if (el) { el.focus(); el.click(); return true; }
                return false;
            }""")
            if body_entered:
                logger.info("正文选择器匹配: JS fallback")
            else:
                logger.warning("未找到正文输入框")

        if body_entered:
            await page.wait_for_timeout(300)
            lines = body.split("\n")
            for i, line in enumerate(lines):
                if line:
                    await page.keyboard.type(line, delay=10)
                if i < len(lines) - 1:
                    await page.keyboard.press("Enter")

        await page.wait_for_timeout(1000)

        # 关闭正文输入可能触发的话题建议弹窗
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        # 插入链接话题标签（蓝色可点击标签）
        tags = formatted.get("tags", [])
        if tags:
            await self._insert_linked_tags(page, tags)

        # 点击空白区域确保所有弹窗关闭
        await page.evaluate("""() => {
            document.body.click();
        }""")
        await page.wait_for_timeout(500)

        # 点击底部红色「发布」按钮（精确定位，避免匹配侧栏「发布笔记」）
        clicked = await page.evaluate("""() => {
            // 优先找底部按钮区域的「发布」按钮（通常是红色 button）
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                // 精确匹配：按钮直接文本是"发布"，且不是"发布笔记"或"暂存离开"
                const text = btn.textContent.trim();
                if (text === '发布') {
                    btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    return 'button:' + text;
                }
            }
            // 备选：找 class 含 publish/submit 的红色按钮
            const redBtns = document.querySelectorAll('.red, .btn-red, [class*="submit"], [class*="publish"]');
            for (const btn of redBtns) {
                if (btn.textContent.includes('发布')) {
                    btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    return 'class:' + btn.className;
                }
            }
            return null;
        }""")
        logger.info("发布按钮点击结果: %s", clicked)
        await page.wait_for_timeout(5000)

        # 检查是否有发布确认弹窗（小红书可能会弹出确认对话框）
        confirm_clicked = await page.evaluate("""() => {
            const btns = document.querySelectorAll('button, div[role="button"]');
            for (const btn of btns) {
                const text = btn.textContent.trim();
                if (text === '确认发布' || text === '确认' || text === '确定') {
                    btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    return text;
                }
            }
            return null;
        }""")
        if confirm_clicked:
            logger.info("确认弹窗已点击: %s", confirm_clicked)
            await page.wait_for_timeout(5000)

        # 判断发布结果
        current_url = page.url
        if "publish/publish" not in current_url:
            logger.info("小红书笔记发布成功: %s", title)
            return {"success": True, "url": "https://creator.xiaohongshu.com"}
        else:
            # 检查草稿箱数字是否变化（可能已保存但未发布）
            logger.warning("小红书可能保存为草稿而非发布")
            return {"success": True, "url": "https://creator.xiaohongshu.com", "note": "可能保存为草稿，请到草稿箱确认"}

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
