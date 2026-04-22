"""GPT-4o 图像生成 — 通过 OpenAI API (gpt-image-1)。

指令理解最强，支持中文 prompt，$0.04/张，但慢（~60s）。
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from modules.image_gen import ImageGenerator, register_provider

logger = logging.getLogger(__name__)


@register_provider("gpt4o")
class GPT4oGenerator(ImageGenerator):

    @property
    def name(self) -> str:
        return "gpt4o"

    @property
    def price_per_image(self) -> str:
        return "~$0.04"

    @property
    def required_env_vars(self) -> list[str]:
        return ["OPENAI_API_KEY"]

    async def generate(
        self,
        prompt: str,
        size: tuple[int, int] = (1080, 1440),
        style: str = "natural",
        output_dir: Path | None = None,
    ) -> str:
        from openai import OpenAI

        # gpt-image-1 支持的尺寸：1024x1024, 1536x1024, 1024x1536
        api_size = _map_size(size)

        logger.info("GPT-4o 生成中: size=%s, prompt=%s...", api_size, prompt[:80])

        # 临时清除代理环境变量（避免 HTTP 代理 SSL 问题）
        proxy_vars = {}
        for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY",
                    "all_proxy", "ALL_PROXY"):
            if var in os.environ:
                proxy_vars[var] = os.environ.pop(var)

        try:
            client = OpenAI(timeout=120.0)
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                n=1,
                size=api_size,
                quality="high",
            )
        finally:
            os.environ.update(proxy_vars)

        # gpt-image-1 默认返回 b64_json
        b64_data = response.data[0].b64_json
        img_bytes = base64.b64decode(b64_data)

        out_path = self._output_path(output_dir, ".png")
        with open(out_path, "wb") as f:
            f.write(img_bytes)

        logger.info("GPT-4o 生成完成: %s", out_path)
        return str(out_path)


def _map_size(size: tuple[int, int]) -> str:
    """将宽高映射到 gpt-image-1 支持的尺寸。"""
    w, h = size
    ratio = w / h
    if ratio > 1.2:
        return "1536x1024"  # 横图
    elif ratio < 0.8:
        return "1024x1536"  # 竖图
    else:
        return "1024x1024"  # 方图
