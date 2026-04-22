"""Xiaohongshu data scraper.

Provides two scraping modes:
1. HTTP API mode: Uses XHS web API endpoints with cookie authentication
2. Manual import mode: Loads data from exported JSON files

XHS web API endpoints used:
- Search:  /api/sns/web/v1/search/notes
- Note:    /api/sns/web/v1/feed
- User:    /api/sns/web/v1/user_posted

Requires a valid XHS web cookie (set via XHS_COOKIE env var or config).
Implements rate limiting to respect the platform.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from models.competitor import CompetitorAccount, ScrapedNote

logger = logging.getLogger(__name__)

XHS_BASE_URL = "https://edith.xiaohongshu.com"
SCRAPER_DATA_DIR = "data/scraper"

# Default headers mimicking XHS web client
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Origin": "https://www.xiaohongshu.com",
    "Referer": "https://www.xiaohongshu.com/",
    "Content-Type": "application/json;charset=UTF-8",
}


@dataclass
class ScraperConfig:
    """Configuration for the XHS scraper."""

    cookie: str = ""
    rate_limit: float = 2.0  # seconds between requests
    max_notes_per_search: int = 40
    max_notes_per_user: int = 50
    data_dir: str = SCRAPER_DATA_DIR
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> ScraperConfig:
        return cls(
            cookie=os.getenv("XHS_COOKIE", ""),
            rate_limit=float(os.getenv("XHS_RATE_LIMIT", "2.0")),
            max_notes_per_search=int(os.getenv("XHS_MAX_SEARCH", "40")),
            max_notes_per_user=int(os.getenv("XHS_MAX_USER_NOTES", "50")),
            data_dir=os.getenv("XHS_DATA_DIR", SCRAPER_DATA_DIR),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.cookie)


class XhsScraper:
    """Xiaohongshu data scraper with rate limiting and local caching.

    Usage:
        scraper = XhsScraper(config)

        # Search notes by keyword
        notes = scraper.search_notes("AI工具推荐", count=20)

        # Scrape a user's posted notes
        notes = scraper.scrape_user_notes(user_id="xxx", count=30)

        # Load from exported file (no cookie needed)
        notes = scraper.import_from_file("exported_notes.json")
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._client: httpx.Client | None = None
        self._last_request_time: float = 0
        os.makedirs(config.data_dir, exist_ok=True)

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            headers = {**DEFAULT_HEADERS}
            if self.config.cookie:
                headers["Cookie"] = self.config.cookie
            self._client = httpx.Client(
                base_url=XHS_BASE_URL,
                headers=headers,
                timeout=self.config.timeout,
                follow_redirects=True,
            )
        return self._client

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.config.rate_limit:
            sleep_time = self.config.rate_limit - elapsed
            logger.debug("Rate limiting: sleeping %.1fs", sleep_time)
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Make a rate-limited request to XHS API."""
        if not self.config.is_configured:
            logger.error("XHS cookie not configured. Set XHS_COOKIE env var.")
            return None

        self._rate_limit()
        client = self._get_client()

        try:
            resp = client.request(method, path, **kwargs)
            resp.raise_for_status()
            data = resp.json()

            if data.get("success") is False or data.get("code") != 0:
                logger.warning(
                    "XHS API error: code=%s msg=%s",
                    data.get("code"),
                    data.get("msg"),
                )
                return None

            return data.get("data", data)

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error %d: %s", e.response.status_code, path)
            return None
        except httpx.RequestError as e:
            logger.error("Request error: %s", e)
            return None
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from %s", path)
            return None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_notes(
        self,
        keyword: str,
        count: int | None = None,
        sort: str = "general",
        note_type: int = 0,
    ) -> list[ScrapedNote]:
        """Search notes by keyword.

        Args:
            keyword: Search query string.
            count: Max notes to return (default: config.max_notes_per_search).
            sort: Sort order - "general" (default), "time_descending",
                  "popularity_descending".
            note_type: 0=all, 1=image, 2=video.

        Returns:
            List of ScrapedNote objects.
        """
        count = count or self.config.max_notes_per_search
        notes: list[ScrapedNote] = []
        cursor = ""
        page = 0

        logger.info("Searching XHS: '%s' (max %d notes)", keyword, count)

        while len(notes) < count:
            page += 1
            payload = {
                "keyword": keyword,
                "page": page,
                "page_size": 20,
                "search_id": "",
                "sort": sort,
                "note_type": note_type,
            }
            if cursor:
                payload["cursor"] = cursor

            data = self._request("POST", "/api/sns/web/v1/search/notes", json=payload)
            if not data:
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                note_card = item.get("note_card", {})
                note = self._parse_search_note(item.get("id", ""), note_card)
                if note:
                    notes.append(note)

            cursor = data.get("cursor", "")
            has_more = data.get("has_more", False)
            if not has_more:
                break

            logger.info("Search page %d: got %d notes total", page, len(notes))

        notes = notes[:count]
        self._save_notes(notes, f"search_{keyword}")
        logger.info("Search complete: %d notes for '%s'", len(notes), keyword)
        return notes

    def _parse_search_note(
        self, note_id: str, card: dict[str, Any]
    ) -> ScrapedNote | None:
        """Parse a note from search results."""
        if not card:
            return None

        interact = card.get("interact_info", {})
        user = card.get("user", {})

        note = ScrapedNote(
            note_id=note_id or card.get("note_id", ""),
            title=card.get("display_title", ""),
            body=card.get("desc", ""),
            author_id=user.get("user_id", ""),
            author_name=user.get("nickname", ""),
            likes=self._parse_count(interact.get("liked_count", "0")),
            comments=self._parse_count(interact.get("comment_count", "0")),
            shares=self._parse_count(interact.get("share_count", "0")),
            saves=self._parse_count(interact.get("collected_count", "0")),
            tags=[
                t.get("name", "") for t in card.get("tag_list", []) if t.get("name")
            ],
            cover_url=card.get("cover", {}).get("url", ""),
            note_type="video" if card.get("type") == "video" else "text_image",
        )
        note.compute_metrics()
        return note

    # ------------------------------------------------------------------
    # User notes
    # ------------------------------------------------------------------

    def scrape_user_notes(
        self, user_id: str, count: int | None = None
    ) -> list[ScrapedNote]:
        """Scrape a user's posted notes.

        Args:
            user_id: XHS user ID.
            count: Max notes to return.

        Returns:
            List of ScrapedNote objects sorted by total_interactions desc.
        """
        count = count or self.config.max_notes_per_user
        notes: list[ScrapedNote] = []
        cursor = ""

        logger.info("Scraping user %s notes (max %d)", user_id, count)

        while len(notes) < count:
            params = {
                "user_id": user_id,
                "cursor": cursor,
                "num": 30,
                "image_formats": "jpg,webp,avif",
            }

            data = self._request("GET", "/api/sns/web/v1/user_posted", params=params)
            if not data:
                break

            items = data.get("notes", [])
            if not items:
                break

            for item in items:
                note = self._parse_user_note(item, user_id)
                if note:
                    notes.append(note)

            cursor = data.get("cursor", "")
            has_more = data.get("has_more", False)
            if not has_more:
                break

        notes = notes[:count]
        notes.sort(key=lambda n: n.total_interactions, reverse=True)
        self._save_notes(notes, f"user_{user_id}")
        logger.info("User scrape complete: %d notes for user %s", len(notes), user_id)
        return notes

    def _parse_user_note(
        self, item: dict[str, Any], user_id: str
    ) -> ScrapedNote | None:
        """Parse a note from user posted list."""
        if not item:
            return None

        interact = item.get("interact_info", {})
        user = item.get("user", {})

        note = ScrapedNote(
            note_id=item.get("note_id", ""),
            title=item.get("display_title", ""),
            body=item.get("desc", ""),
            author_id=user_id,
            author_name=user.get("nickname", ""),
            likes=self._parse_count(interact.get("liked_count", "0")),
            saves=self._parse_count(interact.get("collected_count", "0")),
            comments=self._parse_count(interact.get("comment_count", "0")),
            shares=self._parse_count(interact.get("share_count", "0")),
            cover_url=item.get("cover", {}).get("url", ""),
            note_type="video" if item.get("type") == "video" else "text_image",
        )
        note.compute_metrics()
        return note

    # ------------------------------------------------------------------
    # Note detail
    # ------------------------------------------------------------------

    def scrape_note_detail(self, note_id: str) -> ScrapedNote | None:
        """Scrape full detail of a single note.

        Returns a ScrapedNote with body text and all images.
        """
        logger.info("Scraping note detail: %s", note_id)

        payload = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
        }

        data = self._request("POST", "/api/sns/web/v1/feed", json=payload)
        if not data:
            return None

        items = data.get("items", [])
        if not items:
            return None

        item = items[0]
        note_card = item.get("note_card", {})
        interact = note_card.get("interact_info", {})
        user = note_card.get("user", {})

        image_list = note_card.get("image_list", [])
        image_urls = [img.get("url_default", "") for img in image_list if img.get("url_default")]

        tag_list = note_card.get("tag_list", [])
        tags = [t.get("name", "") for t in tag_list if t.get("name")]

        note = ScrapedNote(
            note_id=note_id,
            title=note_card.get("title", ""),
            body=note_card.get("desc", ""),
            author_id=user.get("user_id", ""),
            author_name=user.get("nickname", ""),
            likes=self._parse_count(interact.get("liked_count", "0")),
            saves=self._parse_count(interact.get("collected_count", "0")),
            comments=self._parse_count(interact.get("comment_count", "0")),
            shares=self._parse_count(interact.get("share_count", "0")),
            views=self._parse_count(interact.get("view_count", "0")),
            tags=tags,
            cover_url=image_urls[0] if image_urls else "",
            image_urls=image_urls,
            note_type="video" if note_card.get("type") == "video" else "text_image",
            published_at=note_card.get("time", ""),
        )
        note.compute_metrics()
        return note

    # ------------------------------------------------------------------
    # Import from file (no cookie needed)
    # ------------------------------------------------------------------

    def import_from_file(self, file_path: str) -> list[ScrapedNote]:
        """Import notes from a JSON file.

        Supports two formats:
        1. List of note dicts: [{"note_id": ..., "title": ..., ...}, ...]
        2. Wrapped format: {"notes": [...]} or {"data": {"items": [...]}}

        This is useful when you export data from other tools or manually
        collect notes into a JSON file.
        """
        if not os.path.exists(file_path):
            logger.error("Import file not found: %s", file_path)
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Detect format
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("notes", raw.get("items", raw.get("data", {}).get("items", [])))
            if not isinstance(items, list):
                items = [raw]
        else:
            logger.error("Unsupported import format in %s", file_path)
            return []

        notes = []
        for item in items:
            try:
                note = ScrapedNote.from_dict(item)
                note.compute_metrics()
                notes.append(note)
            except (TypeError, KeyError) as e:
                logger.warning("Skipping malformed note: %s", e)

        logger.info("Imported %d notes from %s", len(notes), file_path)
        return notes

    def import_competitor_from_file(self, file_path: str) -> CompetitorAccount | None:
        """Import a competitor account from a JSON file."""
        if not os.path.exists(file_path):
            logger.error("Import file not found: %s", file_path)
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            return CompetitorAccount.from_dict(data)
        except (TypeError, KeyError) as e:
            logger.error("Failed to parse competitor data: %s", e)
            return None

    # ------------------------------------------------------------------
    # Export / persistence
    # ------------------------------------------------------------------

    def _save_notes(self, notes: list[ScrapedNote], label: str) -> str:
        """Save scraped notes to a JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{label}_{timestamp}.json"
        filepath = os.path.join(self.config.data_dir, filename)
        os.makedirs(self.config.data_dir, exist_ok=True)

        data = {
            "label": label,
            "scraped_at": datetime.now().isoformat(),
            "count": len(notes),
            "notes": [n.to_dict() for n in notes],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("Saved %d notes to %s", len(notes), filepath)
        return filepath

    def export_notes(self, notes: list[ScrapedNote], filename: str) -> str:
        """Export notes to a named JSON file."""
        filepath = os.path.join(self.config.data_dir, filename)
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

        data = {
            "exported_at": datetime.now().isoformat(),
            "count": len(notes),
            "notes": [n.to_dict() for n in notes],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return filepath

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_count(value: Any) -> int:
        """Parse engagement count strings like '1.2万' into integers."""
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)

        s = str(value).strip()
        if not s or s == "-":
            return 0

        try:
            if "万" in s:
                return int(float(s.replace("万", "")) * 10000)
            elif "亿" in s:
                return int(float(s.replace("亿", "")) * 100000000)
            return int(float(s))
        except (ValueError, TypeError):
            return 0

    def get_cached_notes(self, label: str) -> list[ScrapedNote]:
        """Load the most recent cached notes for a given label."""
        if not os.path.exists(self.config.data_dir):
            return []

        files = sorted(
            [
                f
                for f in os.listdir(self.config.data_dir)
                if f.startswith(label) and f.endswith(".json")
            ],
            reverse=True,
        )

        if not files:
            return []

        filepath = os.path.join(self.config.data_dir, files[0])
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [ScrapedNote.from_dict(n) for n in data.get("notes", [])]

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> XhsScraper:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
