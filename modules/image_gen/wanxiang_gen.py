"""通义万相图片生成 — 通过阿里云灵积 DashScope API。

中文理解最强，国内合规，支持 wanx2.1-t2i-turbo / wanx2.1-t2i-plus。
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from modules.image_gen import ImageGenerator, register_provider

logger = logging.getLogger(__name__)


@register_provider("wanxiang")
class WanxiangGenerator(ImageGenerator):

    @property
    def name(self) -> str:
        return "wanxiang"

    @property
    def price_per_image(self) -> str:
        return "按 token 计费"

    @property
    def required_env_vars(self) -> list[str]:
        return ["DASHSCOPE_API_KEY"]

    async def generate(
        self,
        prompt: str,
        size: tuple[int, int] = (1080, 1440),
        style: str = "natural",
        output_dir: Path | None = None,
    ) -> str:
        import httpx

        api_key = os.environ["DASHSCOPE_API_KEY"]

        # 通义万相支持的尺寸
        api_size = _map_size(size)
        model = "wanx2.1-t2i-turbo"

        logger.info("通义万相生成中: model=%s, size=%s, prompt=%s...",
                     model, api_size, prompt[:80])

        # 异步提交任务
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json={
                    "model": model,
                    "input": {
                        "prompt": prompt,
                    },
                    "parameters": {
                        "size": api_size,
                        "n": 1,
                    },
                },
            )
            resp.raise_for_status()
            task_data = resp.json()

        task_id = task_data.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"通义万相未返回 task_id: {task_data}")

        logger.info("通义万相任务已提交: task_id=%s", task_id)

        # 轮询等待结果
        import asyncio
        for _ in range(120):  # 最多等 2 分钟
            await asyncio.sleep(2)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                result = resp.json()

            status = result.get("output", {}).get("task_status")
            if status == "SUCCEEDED":
                break
            elif status == "FAILED":
                msg = result.get("output", {}).get("message", "未知错误")
                raise RuntimeError(f"通义万相生成失败: {msg}")
            # PENDING / RUNNING 继续等待
        else:
            raise RuntimeError("通义万相生成超时（2分钟）")

        # 下载结果图片
        results = result.get("output", {}).get("results", [])
        if not results:
            raise RuntimeError(f"通义万相返回空结果: {result}")

        img_url = results[0].get("url")
        if not img_url:
            raise RuntimeError(f"通义万相未返回图片 URL: {results[0]}")

        out_path = self._output_path(output_dir, ".png")
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(img_url)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(resp.content)

        logger.info("通义万相生成完成: %s", out_path)
        return str(out_path)


def _map_size(size: tuple[int, int]) -> str:
    """将宽高映射到通义万相支持的尺寸。"""
    w, h = size
    ratio = w / h
    # 通义万相支持: 1024*1024, 720*1280, 1280*720
    if ratio > 1.2:
        return "1280*720"
    elif ratio < 0.8:
        return "720*1280"
    else:
        return "1024*1024"
