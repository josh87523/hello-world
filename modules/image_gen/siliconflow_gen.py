"""SiliconFlow 图片生成 — REST API，最便宜。

聚合平台，支持 Flux、Kolors 等模型，$0.015/张起。
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from modules.image_gen import ImageGenerator, register_provider

logger = logging.getLogger(__name__)

# SiliconFlow 上的模型
SF_MODELS = {
    "flux-schnell": "black-forest-labs/FLUX.1-schnell",
    "flux-dev": "black-forest-labs/FLUX.1-dev",
    "sd-xl": "stabilityai/stable-diffusion-xl-base-1.0",
    "sd-3-medium": "stabilityai/stable-diffusion-3-medium",
}

DEFAULT_MODEL = "flux-schnell"


@register_provider("siliconflow")
class SiliconFlowGenerator(ImageGenerator):

    @property
    def name(self) -> str:
        return "siliconflow"

    @property
    def price_per_image(self) -> str:
        return "~$0.015"

    @property
    def required_env_vars(self) -> list[str]:
        return ["SILICONFLOW_API_KEY"]

    async def generate(
        self,
        prompt: str,
        size: tuple[int, int] = (1080, 1440),
        style: str = "natural",
        output_dir: Path | None = None,
    ) -> str:
        import httpx

        api_key = os.environ["SILICONFLOW_API_KEY"]
        model = SF_MODELS[DEFAULT_MODEL]

        # SiliconFlow 的 Flux 模型用 image_size 参数
        w, h = size
        # 限制到合理尺寸
        if w > 1024:
            ratio = 1024 / w
            w = 1024
            h = int(h * ratio)
        if h > 1024:
            ratio = 1024 / h
            h = 1024
            w = int(w * ratio)

        logger.info("SiliconFlow 生成中: model=%s, %dx%d, prompt=%s...",
                     model, w, h, prompt[:80])

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.siliconflow.cn/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "prompt": prompt,
                    "image_size": f"{w}x{h}",
                    "num_inference_steps": 20,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        # 响应格式：{"images": [{"url": "..."} 或 {"b64_json": "..."}]}
        images = data.get("images", data.get("data", []))
        if not images:
            raise RuntimeError(f"SiliconFlow 返回空结果: {data}")

        img = images[0]
        out_path = self._output_path(output_dir, ".png")

        if "url" in img:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(img["url"])
                resp.raise_for_status()
                with open(out_path, "wb") as f:
                    f.write(resp.content)
        elif "b64_json" in img:
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(img["b64_json"]))
        else:
            raise RuntimeError(f"SiliconFlow 未知响应格式: {img.keys()}")

        logger.info("SiliconFlow 生成完成: %s", out_path)
        return str(out_path)
