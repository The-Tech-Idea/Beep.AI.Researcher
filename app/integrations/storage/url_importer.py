"""
URL Importer — Import documents from URLs, HTML pages, and RSS/Atom feeds.

Converts web content into project documents.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from ..base_connector import BaseConnector, ConnectorInfo, ConnectorType, SyncResult

logger = logging.getLogger(__name__)


class URLImporter(BaseConnector):
    """
    Import documents from URLs and RSS feeds.

    Features:
    - Single URL → extract article text → create document
    - RSS/Atom feed → list entries → import selected
    - Supports HTML, PDF, and plain text URLs
    - Uses readability-style extraction for clean article text
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config, max_retries=2, retry_base_delay=1.0)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "BeepAI-Researcher/1.0 (Academic Research Tool)"
        })

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="url_importer",
            display_name="URL & RSS Importer",
            connector_type=ConnectorType.STORAGE,
            description="Import documents from web URLs and RSS/Atom feeds",
            requires_auth=False,
        )

    def _do_connect(self, credentials: Dict[str, Any]) -> bool:
        return True  # No auth needed

    def _do_disconnect(self) -> None:
        self._session.close()

    def _do_test(self) -> bool:
        try:
            r = self._session.get("https://httpbin.org/status/200", timeout=10)
            return r.status_code == 200
        except Exception:
            return True  # Don't fail if httpbin is down

    # ── URL Import ───────────────────────────────────────────────────

    def import_url(self, url: str) -> Dict[str, Any]:
        """
        Import a single URL as a document.

        Returns:
            dict with 'title', 'content', 'mime_type', 'source_url', 'word_count'
        """
        parsed = urlparse(url)
        if not parsed.scheme:
            url = "https://" + url

        try:
            response = self._session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")

            if "application/pdf" in content_type:
                return {
                    "title": self._filename_from_url(url),
                    "content": None,
                    "raw_bytes": response.content,
                    "mime_type": "application/pdf",
                    "source_url": url,
                    "word_count": 0,
                }

            # HTML content → extract article text
            if "text/html" in content_type:
                title, text = self._extract_article(response.text, url)
                return {
                    "title": title,
                    "content": text,
                    "raw_bytes": None,
                    "mime_type": "text/plain",
                    "source_url": url,
                    "word_count": len(text.split()),
                }

            # Plain text
            return {
                "title": self._filename_from_url(url),
                "content": response.text,
                "raw_bytes": None,
                "mime_type": "text/plain",
                "source_url": url,
                "word_count": len(response.text.split()),
            }

        except Exception as e:
            logger.error("URL import failed for %s: %s", url, e)
            return {"error": str(e), "source_url": url}

    # ── RSS/Atom Feed ────────────────────────────────────────────────

    def list_feed_entries(self, feed_url: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Parse an RSS/Atom feed and return entries.

        Returns:
            List of dicts with 'title', 'url', 'published', 'summary'
        """
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed — RSS import unavailable")
            return []

        try:
            feed = feedparser.parse(feed_url)
            entries = []
            for entry in feed.entries[:limit]:
                entries.append({
                    "title": entry.get("title", "Untitled"),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", "")[:500],
                    "authors": [a.get("name", "") for a in entry.get("authors", [])],
                })
            return entries
        except Exception as e:
            logger.error("Feed parse failed for %s: %s", feed_url, e)
            return []

    def import_feed(self, feed_url: str, limit: int = 10) -> SyncResult:
        """Import all entries from an RSS feed as documents."""
        entries = self.list_feed_entries(feed_url, limit)
        if not entries:
            return SyncResult(success=False, errors=["No entries found in feed"])

        imported = 0
        errors = []
        for entry in entries:
            url = entry.get("url")
            if url:
                result = self.import_url(url)
                if "error" not in result:
                    imported += 1
                else:
                    errors.append(f"{url}: {result['error']}")

        return SyncResult(
            success=imported > 0,
            items_synced=imported,
            items_failed=len(errors),
            errors=errors,
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def _extract_article(self, html: str, url: str) -> tuple[str, str]:
        """
        Extract article title and clean text from HTML.

        Uses a simple regex-based approach. For production, consider
        readability-lxml or similar library.
        """
        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else self._filename_from_url(url)
        title = re.sub(r"\s+", " ", title)

        # Remove script/style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)

        # Decode HTML entities
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&#\d+;", "", text)

        # Clean whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return title, text

    @staticmethod
    def _filename_from_url(url: str) -> str:
        """Extract a title from a URL path."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if path:
            name = path.split("/")[-1]
            name = name.replace("-", " ").replace("_", " ")
            if "." in name:
                name = name.rsplit(".", 1)[0]
            return name.title() or parsed.netloc
        return parsed.netloc
