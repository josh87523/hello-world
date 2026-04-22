"""Abstract base class for platform adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from models.content import ContentFinal, Platform


class PlatformAdapter(ABC):
    """Base interface for all platform adapters.

    Each platform (Xiaohongshu, WeChat, Douyin, etc.) implements this interface.
    This makes it trivial to add new platforms without changing the core workflow.

    To add a new platform:
        1. Create a new file in platforms/ (e.g., platforms/wechat.py)
        2. Implement the PlatformAdapter interface
        3. Register it in PlatformRegistry
    """

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """The platform this adapter handles."""
        ...

    @abstractmethod
    def format_content(self, content: ContentFinal) -> dict[str, Any]:
        """Format content according to platform specifications.

        Returns a dict with platform-specific fields ready for publishing.
        """
        ...

    @abstractmethod
    def validate_content(self, content: ContentFinal) -> list[str]:
        """Validate content against platform rules.

        Returns a list of validation errors (empty = valid).
        """
        ...

    @abstractmethod
    def publish(self, content: ContentFinal) -> dict[str, Any]:
        """Publish content to the platform.

        Returns a dict with publish result (url, id, status, etc.).
        """
        ...

    def get_platform_rules(self) -> dict[str, Any]:
        """Return platform-specific content rules and limits."""
        return {}
