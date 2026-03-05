"""Platform adapter registry for dynamic platform support."""

from __future__ import annotations

from typing import Type

from models.content import Platform
from platforms.base import PlatformAdapter


class PlatformRegistry:
    """Registry for platform adapters.

    Usage:
        registry = PlatformRegistry()
        registry.register(XiaohongshuAdapter)
        adapter = registry.get(Platform.XIAOHONGSHU)
    """

    _adapters: dict[Platform, PlatformAdapter] = {}

    @classmethod
    def register(cls, adapter_class: Type[PlatformAdapter]) -> None:
        """Register a platform adapter class."""
        adapter = adapter_class()
        cls._adapters[adapter.platform] = adapter

    @classmethod
    def get(cls, platform: Platform) -> PlatformAdapter:
        """Get the adapter for a platform."""
        adapter = cls._adapters.get(platform)
        if not adapter:
            available = [p.value for p in cls._adapters]
            raise ValueError(
                f"No adapter registered for platform '{platform.value}'. "
                f"Available: {available}"
            )
        return adapter

    @classmethod
    def list_platforms(cls) -> list[Platform]:
        """List all registered platforms."""
        return list(cls._adapters.keys())


# Auto-register built-in adapters
def _register_defaults():
    from platforms.xiaohongshu import XiaohongshuAdapter
    from platforms.twitter import TwitterAdapter
    from platforms.jike import JikeAdapter
    from platforms.threads import ThreadsAdapter
    from platforms.instagram import InstagramAdapter

    PlatformRegistry.register(XiaohongshuAdapter)
    PlatformRegistry.register(TwitterAdapter)
    PlatformRegistry.register(JikeAdapter)
    PlatformRegistry.register(ThreadsAdapter)
    PlatformRegistry.register(InstagramAdapter)


_register_defaults()
