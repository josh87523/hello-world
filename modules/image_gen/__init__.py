"""AI 图片生成模块 — 多 Provider 支持。

支持的 Provider：
  - flux:       Flux 1.1 Pro (via Replicate) — 写实首选
  - gpt4o:      GPT-4o 图像生成 (OpenAI)    — 指令理解最强
  - recraft:    Recraft V3 (via Replicate)   — 文字排版最强
  - siliconflow: SiliconFlow 聚合平台        — 最便宜
  - wanxiang:   通义万相 (阿里云)             — 中文理解最强
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 默认输出目录
DEFAULT_OUTPUT_DIR = Path("/tmp/image_gen")


class ImageGenerator(ABC):
    """图片生成器抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 显示名称。"""
        ...

    @property
    @abstractmethod
    def price_per_image(self) -> str:
        """每张图片大约价格。"""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        size: tuple[int, int] = (1080, 1440),
        style: str = "natural",
        output_dir: Path | None = None,
    ) -> str:
        """生成图片，返回本地文件路径。

        Args:
            prompt: 英文图片描述
            size: (width, height)
            style: 风格提示（natural/vivid/artistic）
            output_dir: 输出目录，默认 /tmp/image_gen/
        """
        ...

    def _output_path(self, output_dir: Path | None, suffix: str = ".png") -> Path:
        """生成输出文件路径。"""
        d = output_dir or DEFAULT_OUTPUT_DIR
        d.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        return d / f"{self.name}_{ts}{suffix}"

    def is_available(self) -> bool:
        """检查 API key 是否已配置。"""
        for key in self.required_env_vars:
            if not os.environ.get(key):
                return False
        return True

    @property
    @abstractmethod
    def required_env_vars(self) -> list[str]:
        """需要的环境变量列表。"""
        ...


# Provider 注册表
_PROVIDERS: dict[str, type[ImageGenerator]] = {}


def register_provider(name: str):
    """装饰器：注册 Provider。"""
    def decorator(cls: type[ImageGenerator]):
        _PROVIDERS[name] = cls
        return cls
    return decorator


def get_provider(name: str) -> ImageGenerator:
    """获取指定 Provider 实例。"""
    if name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"未知 Provider: {name}，可用: {available}")
    return _PROVIDERS[name]()


def get_available_providers() -> dict[str, ImageGenerator]:
    """获取所有已配置 API key 的 Provider。"""
    result = {}
    for name, cls in _PROVIDERS.items():
        inst = cls()
        if inst.is_available():
            result[name] = inst
        else:
            logger.debug("Provider %s 不可用（缺少 API key）", name)
    return result


def list_all_providers() -> dict[str, dict[str, Any]]:
    """列出所有 Provider 及状态。"""
    result = {}
    for name, cls in _PROVIDERS.items():
        inst = cls()
        result[name] = {
            "name": inst.name,
            "price": inst.price_per_image,
            "available": inst.is_available(),
            "env_vars": inst.required_env_vars,
        }
    return result


async def compare_providers(
    prompt: str,
    providers: list[str] | None = None,
    size: tuple[int, int] = (1080, 1440),
    output_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """用同一个 prompt 对比多个 Provider 的生成效果。

    Returns:
        {provider_name: {"path": str, "time": float, "error": str | None}}
    """
    out = output_dir or DEFAULT_OUTPUT_DIR / "compare"

    if providers is None or providers == ["all"]:
        available = get_available_providers()
    else:
        available = {}
        for name in providers:
            inst = get_provider(name)
            if inst.is_available():
                available[name] = inst
            else:
                logger.warning("Provider %s 不可用，跳过", name)

    if not available:
        raise RuntimeError("没有可用的 Provider（请检查环境变量配置）")

    results = {}

    async def _run(name: str, gen: ImageGenerator):
        t0 = time.time()
        try:
            path = await gen.generate(prompt, size=size, output_dir=out)
            elapsed = time.time() - t0
            results[name] = {"path": path, "time": round(elapsed, 1), "error": None}
            logger.info("%s: 生成成功 (%.1fs) → %s", name, elapsed, path)
        except Exception as e:
            elapsed = time.time() - t0
            results[name] = {"path": None, "time": round(elapsed, 1), "error": str(e)}
            logger.error("%s: 生成失败 (%.1fs): %s", name, elapsed, e)

    tasks = [_run(name, gen) for name, gen in available.items()]
    await asyncio.gather(*tasks)

    return results


# 导入所有 Provider（触发注册）
def _load_providers():
    from modules.image_gen import flux_gen  # noqa: F401
    from modules.image_gen import gpt4o_gen  # noqa: F401
    from modules.image_gen import recraft_gen  # noqa: F401
    from modules.image_gen import siliconflow_gen  # noqa: F401
    from modules.image_gen import wanxiang_gen  # noqa: F401


_load_providers()
