"""Flux 1.1 Pro 图片生成 — 通过 Replicate API。

写实图首选，速度快（~4.5s），$0.04/张。
"""

from __future__ import annotations

import logging
from pathlib import Path

from modules.image_gen import ImageGenerator, register_provider

logger = logging.getLogger(__name__)


@register_provider("flux")
class FluxGenerator(ImageGenerator):

    @property
    def name(self) -> str:
        return "flux"

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
        # Flux 用 aspect_ratio 而不是 width/height
        aspect = _closest_aspect_ratio(w, h)

        logger.info("Flux 生成中: aspect=%s, prompt=%s...", aspect, prompt[:80])

        output = replicate.run(
            "black-forest-labs/flux-1.1-pro",
            input={
                "prompt": prompt,
                "aspect_ratio": aspect,
                "output_format": "png",
                "output_quality": 90,
            },
        )

        # output 是 FileOutput，可直接 .read()
        out_path = self._output_path(output_dir, ".png")
        with open(out_path, "wb") as f:
            f.write(output.read())

        logger.info("Flux 生成完成: %s", out_path)
        return str(out_path)


def _closest_aspect_ratio(w: int, h: int) -> str:
    """将宽高映射到 Flux 支持的 aspect_ratio。"""
    ratio = w / h
    options = {
        "1:1": 1.0,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "21:9": 21 / 9,
        "9:21": 9 / 21,
        "2:3": 2 / 3,
        "3:2": 3 / 2,
        "4:5": 4 / 5,
        "5:4": 5 / 4,
    }
    return min(options, key=lambda k: abs(options[k] - ratio))
