"""YouTube video ingester service (Phase 03).

Given a YouTube URL this service:
1. Resolves the video ID and fetches metadata (title, channel, duration)
   via the YouTube Data API v3 if a key is available, or via the public
   oEmbed endpoint as an unauthenticated fallback.
2. Attempts to download the video's auto-generated / manual captions
   using the YouTube Data API (only where the Terms of Service allow).
3. Creates or updates a ``ResearcherDocument`` stub and optionally a
   ``Reference`` record linked to the project.

Heavy processing (STT transcription) is NOT done here — callers that
want STT should enqueue a background task after this returns.

Public API
----------
``ingest_youtube_url(project, url, user_id)``
    Main entry point.  Returns a dict describing what was created.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from app.database import db
from app.models.researcher import ResearchProject, ResearcherDocument, Reference
from app.services.reference_service import create_reference

logger = logging.getLogger(__name__)

# YouTube Data API v3 endpoints
_YT_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
_YT_CAPTION_URL = "https://www.googleapis.com/youtube/v3/captions"
_YT_OEMBED_URL = "https://www.youtube.com/oembed"

# Document source_type value stored in ResearcherDocument
SOURCE_TYPE_YOUTUBE = "youtube"
REFERENCE_SOURCE_TYPE_VIDEO = "video_youtube"

# Maximum caption text stored directly (bytes).  Beyond this size the
# transcript should be written to a document file via storage backend.
_CAPTION_INLINE_LIMIT = 500_000


def _extract_video_id(url: str) -> Optional[str]:
    """Return the YouTube video ID from a URL or None if not recognisable."""
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    # youtu.be/<id>
    if parsed.netloc in ("youtu.be", "www.youtu.be"):
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid or None

    # youtube.com/watch?v=<id>  or  /v/<id>  or  /embed/<id>
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2 and path_parts[0] in ("v", "embed", "shorts"):
        return path_parts[1]

    return None


def _fetch_metadata_api(video_id: str, api_key: str) -> dict[str, Any]:
    """Fetch snippet + contentDetails via YouTube Data API v3."""
    try:
        r = requests.get(
            _YT_VIDEO_URL,
            params={
                "id": video_id,
                "part": "snippet,contentDetails",
                "key": api_key,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or []
        if not items:
            return {}
        item = items[0]
        snippet = item.get("snippet") or {}
        content = item.get("contentDetails") or {}
        return {
            "title": snippet.get("title") or "",
            "channel": snippet.get("channelTitle") or "",
            "description": (snippet.get("description") or "")[:2000],
            "published_at": snippet.get("publishedAt") or "",
            "duration": content.get("duration") or "",
            "thumbnail_url": (
                (snippet.get("thumbnails") or {}).get("high", {}).get("url")
                or (snippet.get("thumbnails") or {}).get("default", {}).get("url")
            ),
        }
    except Exception as exc:
        logger.warning("YouTube Data API metadata fetch failed: %s", exc)
        return {}


def _fetch_metadata_oembed(video_id: str) -> dict[str, Any]:
    """Fallback: fetch title and author via YouTube oEmbed (no key required)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        r = requests.get(
            _YT_OEMBED_URL,
            params={"url": url, "format": "json"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "title": data.get("title") or "",
            "channel": data.get("author_name") or "",
            "description": "",
            "published_at": "",
            "duration": "",
            "thumbnail_url": data.get("thumbnail_url") or "",
        }
    except Exception as exc:
        logger.warning("YouTube oEmbed fallback failed: %s", exc)
        return {}


def _fetch_captions(video_id: str, api_key: str) -> Optional[str]:
    """
    Attempt to list and download auto/manual captions via the Data API.

    Returns plain-text transcript or ``None`` if unavailable (no captions,
    no access, or API error).  Only English captions are tried first; any
    track is used as a last resort.

    This honours YouTube Terms of Service: captions are fetched only via the
    official API, not by scraping.
    """
    try:
        r = requests.get(
            _YT_CAPTION_URL,
            params={"part": "snippet", "videoId": video_id, "key": api_key},
            timeout=15,
        )
        r.raise_for_status()
        tracks = (r.json().get("items") or [])
    except Exception as exc:
        logger.debug("YouTube caption list failed for %s: %s", video_id, exc)
        return None

    if not tracks:
        return None

    # Prefer manual English, then auto English, then any manual, then any auto
    def _priority(track: dict) -> int:
        snip = track.get("snippet") or {}
        lang = (snip.get("language") or "").lower()
        kind = (snip.get("trackKind") or "").lower()
        if lang.startswith("en") and kind == "standard":
            return 0
        if lang.startswith("en") and "asr" in kind:
            return 1
        if kind == "standard":
            return 2
        return 3

    tracks.sort(key=_priority)
    best = tracks[0]
    track_id = best.get("id")
    if not track_id:
        return None

    try:
        dl = requests.get(
            f"{_YT_CAPTION_URL}/{track_id}",
            params={"tfmt": "srt", "key": api_key},
            timeout=30,
        )
        dl.raise_for_status()
        raw = dl.text
        # Strip SRT timestamps to produce plain transcript
        plain = re.sub(r"\d+\s*\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n", "", raw)
        plain = re.sub(r"\n{2,}", "\n", plain).strip()
        return plain[:_CAPTION_INLINE_LIMIT] if plain else None
    except Exception as exc:
        logger.debug("YouTube caption download failed for track %s: %s", track_id, exc)
        return None


def _resolve_api_key(user_id: int) -> Optional[str]:
    """Resolve the YouTube Data API key from the integration credential vault."""
    try:
        from app.models.integrations_registry import SERVICE_TYPE_YOUTUBE
        from app.services.user_integration_connection_service import resolve_user_service_connection

        conn = resolve_user_service_connection(user_id, SERVICE_TYPE_YOUTUBE)
        return conn.get("api_key")
    except Exception:
        return None


def ingest_youtube_url(
    project: ResearchProject,
    url: str,
    *,
    user_id: int,
    create_reference_record: bool = True,
) -> dict[str, Any]:
    """Ingest a YouTube video URL into the project.

    Returns a dict with keys:
    - ``ok`` (bool)
    - ``error`` (str | None)
    - ``video_id`` (str | None)
    - ``document`` (ResearcherDocument | None)
    - ``reference`` (Reference | None)
    - ``transcript_available`` (bool)
    - ``captions_unavailable`` (bool) — True when no captions were found
    - ``stt_hint`` (bool) — True when STT transcription is recommended
    """
    video_id = _extract_video_id(url)
    if not video_id:
        return {"ok": False, "error": "Could not extract a YouTube video ID from the URL."}

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    api_key = _resolve_api_key(user_id)

    # Fetch metadata
    meta: dict[str, Any] = {}
    if api_key:
        meta = _fetch_metadata_api(video_id, api_key)
    if not meta.get("title"):
        meta = _fetch_metadata_oembed(video_id)
    if not meta.get("title"):
        meta = {"title": f"YouTube video {video_id}", "channel": "", "description": ""}

    title: str = meta.get("title") or f"YouTube video {video_id}"
    description: str = meta.get("description") or ""

    # Attempt caption download
    transcript_text: Optional[str] = None
    captions_unavailable = True
    if api_key:
        transcript_text = _fetch_captions(video_id, api_key)
        captions_unavailable = transcript_text is None
    stt_hint = captions_unavailable  # caller can queue STT if available

    # Check for existing document with this source_url
    existing_doc = ResearcherDocument.query.filter_by(
        project_id=project.id,
        source_url=canonical_url,
    ).first()

    if existing_doc:
        # Update transcript if we now have one and didn't before
        if transcript_text and not existing_doc.text_content:
            existing_doc.text_content = transcript_text
            db.session.flush()
        document = existing_doc
    else:
        document = ResearcherDocument(
            project_id=project.id,
            filename=f"{video_id}.txt",
            file_path="",  # no local file for video stubs
            mime_type="text/plain",
            source_type=SOURCE_TYPE_YOUTUBE,
            source_url=canonical_url,
            source_id=video_id,
            text_content=transcript_text,
            status="ready" if transcript_text else "pending",
        )
        db.session.add(document)
        db.session.flush()

    # Create or retrieve associated reference
    reference: Optional[Reference] = None
    if create_reference_record:
        existing_ref = Reference.query.filter_by(
            project_id=project.id,
            url=canonical_url,
        ).first()
        if existing_ref:
            reference = existing_ref
        else:
            try:
                reference = create_reference(
                    project,
                    {
                        "title": title,
                        "authors": [meta.get("channel")] if meta.get("channel") else [],
                        "source_type": REFERENCE_SOURCE_TYPE_VIDEO,
                        "url": canonical_url,
                        "notes": description[:500] if description else "",
                        "metadata": _build_metadata_dict(meta, video_id),
                    },
                    commit=False,
                )
                reference.document_id = document.id
            except Exception as exc:
                logger.warning("Could not create reference for video %s: %s", video_id, exc)

    db.session.commit()

    return {
        "ok": True,
        "error": None,
        "video_id": video_id,
        "document": document,
        "reference": reference,
        "transcript_available": bool(transcript_text),
        "captions_unavailable": captions_unavailable,
        "stt_hint": stt_hint,
        "title": title,
        "thumbnail_url": meta.get("thumbnail_url"),
    }


def _build_metadata_dict(meta: dict[str, Any], video_id: str) -> dict[str, Any]:
    return {
        "provider": "youtube",
        "video_id": video_id,
        "channel": meta.get("channel") or "",
        "duration": meta.get("duration") or "",
        "published_at": meta.get("published_at") or "",
        "thumbnail_url": meta.get("thumbnail_url") or "",
    }
