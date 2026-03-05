"""Recraft V3 图片生成 — 通过 Replicate API。

文字排版最强，支持 SVG，$0.04/张。
"""

from __future__ import annotations

import logging
from pathlib import Path

from modules.image_gen import ImageGenerator, register_provider

logger = logging.getLogger(__name__)


@register_provider("recraft")
class RecraftGenerator(ImageGenerator):

    @property
    def name(self) -> str:
        return "recraft"

    @property
    def price_per_image(self) -> str:
        return "~$0.04"

    @property
    def required_env_vars(self) -> list[str]:
        return ["REPLICATE_API_TOKEN"]

    async def generate(
        self,
        prompt: str,
        size: tuple[int, int] = (1080, 1440),
        style: str = "natural",
        output_dir: Path | None = None,
    ) -> str:
        import replicate

        w, h = size
        # Recraft 用预定义 image_size
        image_size = _closest_image_size(w, h)

        style_map = {
            "natural": "realistic_image",
            "vivid": "digital_illustration",
            "artistic": "digital_illustration",
        }
        recraft_style = style_map.get(style, "realistic_image")

        logger.info("Recraft 生成中: size=%s, style=%s, prompt=%s...",
                     image_size, recraft_style, prompt[:80])

        output = replicate.run(
            "recraft-ai/recraft-v3",
            input={
                "prompt": prompt,
                "image_size": image_size,
                "style": recraft_style,
            },
        )

        out_path = self._output_path(output_dir, ".png")

        # Recraft 返回 FileOutput 或 URL
        if hasattr(output, "read"):
            with open(out_path, "wb") as f:
                f.write(output.read())
        else:
            # output 可能是 URL 字符串
            import httpx
            resp = httpx.get(str(output), timeout=60)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(resp.content)

        logger.info("Recraft 生成完成: %s", out_path)
        return str(out_path)


def _closest_image_size(w: int, h: int) -> str:
    """将宽高映射到 Recraft 支持的 image_size。"""
    ratio = w / h
    if ratio > 1.4:
        return "landscape_16_9"
    elif ratio > 1.1:
        return "landscape_4_3"
    elif ratio < 0.6:
        return "portrait_16_9"
    elif ratio < 0.85:
        return "portrait_4_3"
    else:
        return "square_hd"
