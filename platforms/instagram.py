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
        create_btn = page.locator('[aria-label="New post"], [aria-label="新帖子"], [aria-label="新貼文"]').first
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

        # 点 Next/继续（跳过裁剪和滤镜，需要点两次）
        for i in range(2):
            clicked = await page.evaluate("""() => {
                const btns = document.querySelectorAll('div[role="button"], button, span');
                for (const btn of btns) {
                    const text = btn.textContent.trim();
                    if (text === 'Next' || text === '下一步' || text === '继续' || text === '下一個' || text === '繼續') {
                        btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                        return text;
                    }
                }
                return null;
            }""")
            logger.info("Next 按钮 #%d: %s", i+1, clicked)
            await page.wait_for_timeout(2000)

        # 输入 caption（尝试多种选择器）
        caption_found = False
        for selector in [
            '[aria-label="Write a caption..."]',
            '[aria-label="写说明..."]',
            '[aria-label="撰寫說明..."]',
            '[contenteditable="true"]',
            'textarea',
        ]:
            try:
                caption_input = page.locator(selector).first
                await caption_input.click(timeout=3000)
                caption_found = True
                logger.info("Caption 选择器匹配: %s", selector)
                break
            except Exception:
                continue

        if not caption_found:
            await page.screenshot(path="/tmp/ig_debug_caption_fail.png")
            return {"success": False, "error": "未找到 caption 输入框"}

        await page.wait_for_timeout(500)

        lines = body.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=10)
            if i < len(lines) - 1:
                await page.keyboard.press("Enter")

        await page.wait_for_timeout(1000)

        # 分享 — 精确匹配对话框头部的「分享」按钮（不是"分享到"区域）
        # 截图分析：「分享」是右上角蓝色文字按钮，在 "创建新帖子" 标题旁边
        share_result = await page.evaluate("""() => {
            // 策略1: 查找 header 区域中精确匹配 "分享"/"Share" 的元素
            const allEls = document.querySelectorAll('div[role="button"], button, span, a');
            const candidates = [];
            for (const el of allEls) {
                const text = el.textContent.trim();
                // 精确匹配：只匹配 "分享" 或 "Share"，排除 "分享到" 等
                if (text === '分享' || text === 'Share') {
                    candidates.push(el);
                }
            }
            // 优先选择在页面顶部的元素（header 中的分享按钮 y 坐标较小）
            candidates.sort((a, b) => {
                const ra = a.getBoundingClientRect();
                const rb = b.getBoundingClientRect();
                return ra.top - rb.top;
            });
            if (candidates.length > 0) {
                const btn = candidates[0];
                btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                const rect = btn.getBoundingClientRect();
                return 'clicked:' + btn.textContent.trim() + ' at y=' + Math.round(rect.top);
            }
            return null;
        }""")
        logger.info("Share 按钮点击结果: %s", share_result)

        # 等待分享完成 — 轮询检测状态（最长 30s）
        for attempt in range(15):
            await page.wait_for_timeout(2000)

            status = await page.evaluate("""() => {
                const all = document.querySelectorAll('span, div, h2, img[alt]');
                for (const el of all) {
                    const t = (el.textContent || el.getAttribute('alt') || '').trim();
                    // 成功信号
                    if (t.includes('shared') || t.includes('已分享') ||
                        t.includes('Your post') || t.includes('你的帖子') ||
                        t.includes('Your reel') || t.includes('Post shared') ||
                        t.includes('帖子已分享')) {
                        return 'success:' + t;
                    }
                    // 正在进行中
                    if (t === '正在分享' || t === 'Sharing' || t === 'Sharing...') {
                        return 'sharing';
                    }
                }
                // 检查 Share/分享 按钮是否仍可点击（未开始分享）
                const btns = document.querySelectorAll('div[role="button"], button');
                for (const btn of btns) {
                    const t = btn.textContent.trim();
                    if (t === 'Share' || t === '分享') {
                        return 'share_visible';
                    }
                }
                // 弹窗可能已关闭（分享完成后回到主页）
                return 'dialog_closed';
            }""")

            logger.info("分享状态检测 #%d: %s", attempt + 1, status)

            if status and status.startswith('success:'):
                logger.info("Instagram 发布成功确认: %s", status)
                return {"success": True, "url": "https://www.instagram.com"}

            if status == 'sharing':
                continue  # 仍在上传，继续等

            if status == 'dialog_closed':
                # 弹窗消失 = 分享完成
                logger.info("Instagram 发布完成（对话框已关闭）")
                return {"success": True, "url": "https://www.instagram.com"}

            if status == 'share_visible':
                # Share 按钮仍在，可能点击没生效
                if attempt < 5:
                    continue  # 再等一会
                break

        # 超时 — 截图调试
        await page.screenshot(path="/tmp/ig_debug_after_share.png")
        logger.warning("Instagram 分享超时，截图: /tmp/ig_debug_after_share.png")
        return {"success": False, "error": "分享超时。截图: /tmp/ig_debug_after_share.png"}

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
