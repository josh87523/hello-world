"""微信公众号平台适配器 — 浏览器自动化发布。

公众号 session 在 Chrome 重启后会失效，因此发布时检测到未登录会
自动等待用户在浏览器中扫码重新登录，然后继续发布。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from models.content import ContentFinal, Platform
from platforms.browser_base import (
    BrowserPlatformAdapter,
    launch_chrome_cdp,
    close_chrome_cdp,
)

logger = logging.getLogger(__name__)

WECHAT_TITLE_MAX = 64
WECHAT_SUMMARY_MAX = 120


class WechatOAAdapter(BrowserPlatformAdapter):
    """微信公众号 mp.weixin.qq.com 浏览器自动化发布。"""

    @property
    def platform(self) -> Platform:
        return Platform.WECHAT

    def format_content(self, content: ContentFinal) -> dict[str, Any]:
        title = content.title[:WECHAT_TITLE_MAX]
        body = content.body

        return {
            "platform": "wechat",
            "title": title,
            "body": body,
            "tags": content.tags[:3],
            "images": content.image_urls,
            "cover_image": content.cover_image_url,
        }

    def validate_content(self, content: ContentFinal) -> list[str]:
        errors = []
        if not content.title:
            errors.append("标题不能为空")
        if not content.body:
            errors.append("正文不能为空")
        return errors

    async def _check_login(self, page) -> bool:
        """检查是否已登录。导航到首页后验证。"""
        await page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(5000)

        if "/cgi-bin/home" in page.url or "/cgi-bin/frame" in page.url:
            return True

        return False

    async def _wait_for_login(self, page, timeout: int = 180) -> bool:
        """等待用户扫码登录。返回是否登录成功。"""
        logger.info("公众号需要扫码登录，请在浏览器中扫码...")
        print("  📱 请在浏览器中扫码登录公众号（等待 %d 秒）..." % timeout)

        for _ in range(timeout):
            await asyncio.sleep(1)
            try:
                current_url = page.url
                if "/cgi-bin/home" in current_url or "/cgi-bin/frame" in current_url:
                    logger.info("公众号登录成功")
                    print("  ✓ 登录成功")
                    return True
            except Exception:
                break

        logger.warning("公众号登录超时")
        return False

    def publish(self, content: ContentFinal) -> dict[str, Any]:
        """同步包装异步发布流程。覆盖基类以使用 headed 模式。"""
        return asyncio.run(self._async_publish(content))

    async def _async_publish(self, content: ContentFinal) -> dict[str, Any]:
        """异步发布流程。公众号始终用 headed 模式（需要扫码）。"""
        errors = self.validate_content(content)
        if errors:
            return {"success": False, "error": f"校验失败: {'; '.join(errors)}"}

        formatted = self.format_content(content)

        # 公众号始终用 headed 模式（session 不持久化，可能需要扫码）
        pw, browser, ctx, proc = await launch_chrome_cdp(
            profile_dir=str(self.profile_dir),
            headless=False,
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            # 检查登录状态
            logged_in = await self._check_login(page)
            if not logged_in:
                # 等待用户扫码
                logged_in = await self._wait_for_login(page)
                if not logged_in:
                    return {
                        "success": False,
                        "error": "公众号登录超时，请重试",
                    }

            result = await self._do_publish(page, formatted)
            return result

        except Exception as e:
            logger.exception("发布到 %s 失败", self.platform.value)
            return {"success": False, "error": str(e)}

        finally:
            await close_chrome_cdp(pw, browser, proc)

    async def _do_publish(self, page, formatted: dict[str, Any]) -> dict[str, Any]:
        title = formatted["title"]
        body = formatted["body"]

        # 确认在首页
        if "/cgi-bin/home" not in page.url and "/cgi-bin/frame" not in page.url:
            await page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

        logger.info("首页 URL: %s", page.url)

        # 从首页 URL 提取 token（公众号所有页面跳转必须带 token）
        token_match = re.search(r'token=(\d+)', page.url)
        if not token_match:
            return {"success": False, "error": "未从首页 URL 中提取到 token"}
        token = token_match.group(1)
        logger.info("提取到 token: %s", token)

        # 点击首页的「文章」按钮进入编辑页
        try:
            article_btn = page.locator('a:has-text("文章"), span:has-text("文章")').first
            await article_btn.click()
            await page.wait_for_timeout(5000)
        except Exception:
            # 备选：直接导航到编辑页（带 token）
            editor_url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&token={token}&lang=zh_CN"
            await page.goto(editor_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(5000)

        logger.info("编辑页 URL: %s", page.url)
        await page.screenshot(path="/tmp/wechat_debug_editor.png")

        # 检查是否回到了登录页
        relogin_el = await page.query_selector('text=请重新登录')
        if relogin_el:
            return {"success": False, "error": "公众号 session 不稳定，编辑页需要重新登录"}

        # 输入标题（contenteditable 区域，placeholder "请在这里输入标题"）
        try:
            title_area = page.locator('[data-placeholder*="标题"], [placeholder*="标题"]').first
            await title_area.click(timeout=5000)
        except Exception:
            # 备选：用 JS 点击包含标题 placeholder 文本的元素
            await page.evaluate("""() => {
                const els = document.querySelectorAll('[contenteditable], input, textarea');
                for (const el of els) {
                    const ph = el.getAttribute('data-placeholder') || el.getAttribute('placeholder') || el.textContent;
                    if (ph && ph.includes('标题')) { el.click(); el.focus(); return; }
                }
                // 第二轮：找所有 contenteditable，第一个通常是标题
                const editables = document.querySelectorAll('[contenteditable="true"]');
                if (editables.length > 0) { editables[0].click(); editables[0].focus(); }
            }""")

        await page.wait_for_timeout(500)
        await page.keyboard.type(title, delay=20)
        await page.wait_for_timeout(500)

        # 输入正文（点击 "从这里开始写正文" 区域）
        # 公众号新版编辑器可能在 iframe 中
        editor_frame = None
        for frame in page.frames:
            if "ueditor" in frame.url or "editor" in frame.url:
                editor_frame = frame
                break

        if editor_frame:
            body_area = editor_frame.locator('[contenteditable="true"], body').first
            await body_area.click()
        else:
            # 尝试点击正文区域（通常是第二个 contenteditable）
            try:
                body_area = page.locator('[data-placeholder*="正文"], [data-placeholder*="写正文"]').first
                await body_area.click(timeout=5000)
            except Exception:
                await page.evaluate("""() => {
                    const editables = document.querySelectorAll('[contenteditable="true"]');
                    // 跳过标题（第一个），点击正文（第二个或更后面的）
                    for (let i = 1; i < editables.length; i++) {
                        editables[i].click();
                        editables[i].focus();
                        return;
                    }
                }""")

        await page.wait_for_timeout(500)

        # 输入正文
        lines = body.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=10)
            if i < len(lines) - 1:
                await page.keyboard.press("Enter")

        await page.wait_for_timeout(2000)
        await page.screenshot(path="/tmp/wechat_debug_content.png")

        # 保存为草稿（按钮文字 "保存为草稿"）
        try:
            save_btn = page.locator('button:has-text("保存为草稿"), span:has-text("保存为草稿")').first
            await save_btn.click(timeout=5000)
            await page.wait_for_timeout(3000)

            logger.info("公众号图文已保存为草稿: %s", title)
            await page.screenshot(path="/tmp/wechat_debug_saved.png")
            return {
                "success": True,
                "url": "https://mp.weixin.qq.com",
                "note": "已保存为草稿，请在公众号后台确认发布",
            }
        except Exception as e:
            await page.screenshot(path="/tmp/wechat_debug_save_fail.png")
            return {"success": False, "error": f"保存草稿失败: {e}"}

    def get_platform_rules(self) -> dict[str, Any]:
        return {
            "title_max_length": WECHAT_TITLE_MAX,
            "summary_max_length": WECHAT_SUMMARY_MAX,
            "tips": [
                "公众号以深度长文为主",
                "标题决定打开率",
                "排版美观很重要",
            ],
        }
