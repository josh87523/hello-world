"""Feishu (Lark) integration for content management.

Uses Feishu Open API to create documents for content review and management.
Docs: https://open.feishu.cn/document/server-docs/docs/docs-overview
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from models.content import ContentFinal

logger = logging.getLogger(__name__)

FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """Client for Feishu/Lark API integration.

    Handles:
    - Creating documents for content review
    - Updating document status
    - Sending notifications via bot

    Usage:
        client = FeishuClient(app_id="xxx", app_secret="xxx")
        doc_url = client.create_content_doc(final_content)
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        folder_token: str = "",
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.folder_token = folder_token
        self._http = httpx.Client(base_url=FEISHU_BASE_URL, timeout=30.0)
        self._tenant_token: str | None = None

    def _get_tenant_token(self) -> str:
        """Get tenant access token for API calls."""
        if self._tenant_token:
            return self._tenant_token

        resp = self._http.post(
            "/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        resp.raise_for_status()
        data = resp.json()

        self._tenant_token = data["tenant_access_token"]
        return self._tenant_token

    def _headers(self) -> dict[str, str]:
        token = self._get_tenant_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def create_content_doc(self, content: ContentFinal) -> str:
        """Create a Feishu document for content review.

        Returns the document URL.
        """
        # Build document content in Feishu block format
        blocks = self._build_doc_blocks(content)

        # Create document
        payload: dict[str, Any] = {
            "title": f"[{content.platform.value}] {content.title}",
            "folder_token": self.folder_token,
        }

        resp = self._http.post(
            "/docx/v1/documents",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        doc_data = resp.json()

        document_id = doc_data["data"]["document"]["document_id"]

        # Add content blocks to the document
        if blocks:
            self._http.post(
                f"/docx/v1/documents/{document_id}/blocks/batch_create",
                headers=self._headers(),
                json={"children": blocks},
            )

        doc_url = f"https://feishu.cn/docx/{document_id}"
        logger.info("Feishu doc created: %s", doc_url)
        return doc_url

    def send_bot_message(
        self,
        webhook_url: str,
        title: str,
        content: str,
    ) -> None:
        """Send a message via Feishu bot webhook.

        Useful for notifications when content is ready for review.
        """
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}},
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content,
                    }
                ],
            },
        }

        resp = httpx.post(webhook_url, json=payload, timeout=10.0)
        resp.raise_for_status()
        logger.info("Bot message sent: %s", title)

    def _build_doc_blocks(self, content: ContentFinal) -> list[dict[str, Any]]:
        """Build Feishu document block structure from content."""
        blocks = []

        # Header with metadata
        blocks.append(self._text_block(
            f"平台: {content.platform.value} | "
            f"质量分: {content.quality_score:.2f} | "
            f"状态: {content.status.value}"
        ))

        # Title
        blocks.append(self._heading_block(content.title, level=2))

        # Body content - split into paragraphs
        for paragraph in content.body.split("\n"):
            if paragraph.strip():
                blocks.append(self._text_block(paragraph))

        # Tags
        if content.tags:
            blocks.append(self._heading_block("标签", level=3))
            blocks.append(self._text_block(" ".join(content.tags)))

        # Quality feedback
        if content.quality_feedback:
            blocks.append(self._heading_block("质量审核反馈", level=3))
            blocks.append(self._text_block(content.quality_feedback))

        return blocks

    @staticmethod
    def _text_block(text: str) -> dict[str, Any]:
        return {
            "block_type": 2,  # text
            "text": {"elements": [{"text_run": {"content": text}}]},
        }

    @staticmethod
    def _heading_block(text: str, level: int = 2) -> dict[str, Any]:
        return {
            "block_type": 4,  # heading
            "heading": {
                "elements": [{"text_run": {"content": text}}],
                "level": level,
            },
        }

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
