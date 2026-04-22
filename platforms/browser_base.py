"""浏览器自动化发布基类 — 使用真实 Chrome CDP。

用用户的真实 Chrome 浏览器（非 Patchright），避免被平台检测到自动化指纹。
每个平台独立的 profile 目录，保留登录态。
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from models.content import ContentFinal, Platform
from platforms.base import PlatformAdapter

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).parent.parent / "profiles"
CDP_PORT = 19333  # 避免跟其他 CDP 冲突

# macOS Chrome 路径
CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def _find_chrome() -> str:
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("未找到 Chrome，请安装 Google Chrome")


async def launch_chrome_cdp(
    profile_dir: str,
    headless: bool = False,
    port: int = CDP_PORT,
):
    """启动真实 Chrome 并通过 CDP 连接，返回 (playwright, browser, context, chrome_process)。"""
    import socket

    # 先清理占用端口的残留进程
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", port))
        s.close()
        logger.warning("端口 %d 已被占用，尝试清理...", port)
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True
        )
        for pid_str in result.stdout.strip().split("\n"):
            if pid_str.strip():
                try:
                    os.kill(int(pid_str.strip()), signal.SIGKILL)
                except (ProcessLookupError, ValueError):
                    pass
        await asyncio.sleep(2)
    except (ConnectionRefusedError, OSError):
        pass  # 端口空闲，正常

    chrome_bin = _find_chrome()

    args = [
        chrome_bin,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-component-update",
        "--window-size=1440,900",
    ]
    if headless:
        args.append("--headless=new")

    # 启动 Chrome 进程
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 等待 CDP 端口就绪
    for _ in range(30):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            break
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.5)
    else:
        proc.kill()
        raise RuntimeError(f"Chrome CDP 端口 {port} 未就绪")

    # Playwright 连接 CDP（临时清除代理，避免 CDP 本地连接走代理返回 400）
    proxy_vars = {}
    for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY",
                "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY"):
        if var in os.environ:
            proxy_vars[var] = os.environ.pop(var)

    try:
        try:
            from patchright.async_api import async_playwright
        except ImportError:
            from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        except Exception:
            await pw.stop()
            proc.kill()
            raise
    finally:
        # 恢复代理环境变量
        os.environ.update(proxy_vars)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()

    logger.info("Chrome CDP 就绪 (port=%d, pid=%d)", port, proc.pid)
    return pw, browser, context, proc


async def close_chrome_cdp(pw, browser, proc):
    """关闭 CDP 连接和 Chrome 进程。"""
    try:
        await browser.close()
    except Exception:
        pass
    try:
        await pw.stop()
    except Exception:
        pass
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    logger.info("Chrome 已关闭")


class BrowserPlatformAdapter(PlatformAdapter):
    """需要浏览器自动化的平台适配器基类。"""

    @property
    def profile_dir(self) -> Path:
        return PROFILES_DIR / self.platform.value

    async def _check_login(self, page) -> bool:
        """检查是否已登录。子类必须实现。"""
        raise NotImplementedError

    async def _do_publish(self, page, formatted: dict[str, Any]) -> dict[str, Any]:
        """执行发布操作。子类必须实现。"""
        raise NotImplementedError

    def publish(self, content: ContentFinal) -> dict[str, Any]:
        """同步包装异步发布流程。"""
        return asyncio.run(self._async_publish(content))

    async def _async_publish(self, content: ContentFinal) -> dict[str, Any]:
        """异步发布流程。"""
        errors = self.validate_content(content)
        if errors:
            return {"success": False, "error": f"校验失败: {'; '.join(errors)}"}

        formatted = self.format_content(content)

        pw, browser, ctx, proc = await launch_chrome_cdp(
            profile_dir=str(self.profile_dir),
            headless=True,
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            if not await self._check_login(page):
                return {
                    "success": False,
                    "error": f"未登录 {self.platform.value}，请先运行: python main.py login -p {self.platform.value}",
                }

            result = await self._do_publish(page, formatted)
            return result

        except Exception as e:
            logger.exception("发布到 %s 失败", self.platform.value)
            return {"success": False, "error": str(e)}

        finally:
            await close_chrome_cdp(pw, browser, proc)
