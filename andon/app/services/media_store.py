"""
Media Store — Download MMS media from Twilio and store permanently.

Supports two storage backends:
  1. AWS S3 (when credentials are configured)
  2. Local filesystem fallback (under andon/media/)

All media files (photos and videos) are downloaded from Twilio using the
account credentials, then uploaded to the configured storage backend.
The permanent URL or file path is returned and stored in the events table.
"""

import logging
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Allowed content types and their file extensions
IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/webm": ".webm",
    "video/3gpp": ".3gp",
}

PHOTO_CONTENT_TYPES = set(IMAGE_TYPES.keys())
VIDEO_CONTENT_TYPES = set(VIDEO_TYPES.keys())
ALL_CONTENT_TYPES = PHOTO_CONTENT_TYPES | VIDEO_CONTENT_TYPES


def _get_twilio_auth() -> tuple | None:
    """Get Twilio HTTP Basic Auth credentials."""
    if settings.twilio_account_sid and settings.twilio_auth_token:
        return (settings.twilio_account_sid, settings.twilio_auth_token)
    return None


def _media_category(content_type: str) -> str:
    """Classify a content type as 'photo', 'video', or 'other'."""
    if content_type in PHOTO_CONTENT_TYPES:
        return "photo"
    if content_type in VIDEO_CONTENT_TYPES:
        return "video"
    return "other"


def _file_extension(content_type: str) -> str:
    """Return the file extension for a content type."""
    ext = IMAGE_TYPES.get(content_type) or VIDEO_TYPES.get(content_type)
    if ext:
        return ext
    # Fall back to mimetypes guess
    guessed = mimetypes.guess_extension(content_type)
    return guessed or ".bin"


def _local_media_dir() -> Path:
    """Get or create the local media directory."""
    media_path = Path(settings.media_dir)
    media_path.mkdir(parents=True, exist_ok=True)
    return media_path


async def store_media(
    media_url: str,
    content_type: str,
    media_sid: str = "",
    index: int = 0,
) -> dict:
    """
    Download media from a Twilio URL and store it permanently.

    Returns a dict with:
      - permanent_url:  The permanent URL (S3 or local path)
      - original_url:   The original Twilio URL
      - content_type:   The MIME type
      - category:       'photo', 'video', or 'other'
      - file_size:      Size in bytes
      - filename:       Generated filename
      - stored:         Where it was stored ('s3' or 'local')
    """
    auth = _get_twilio_auth()
    category = _media_category(content_type)
    ext = _file_extension(content_type)

    # Generate a unique filename
    now = datetime.utcnow()
    filename = f"{now.strftime('%Y%m%d')}_{uuid4().hex[:12]}{ext}"

    result = {
        "original_url": media_url,
        "content_type": content_type,
        "category": category,
        "filename": filename,
        "media_sid": media_sid,
        "index": index,
    }

    # ── Download from Twilio ──
    data = await _download_media(media_url, auth)
    if not data:
        logger.warning("Failed to download media: %s", media_url)
        result["permanent_url"] = media_url  # fall back to original URL
        result["file_size"] = 0
        result["stored"] = "failed"
        return result

    result["file_size"] = len(data)

    # ── Store to S3 (if configured) or local ──
    stored_url = await _store_to_s3(data, filename, content_type)
    if stored_url:
        result["permanent_url"] = stored_url
        result["stored"] = "s3"
    else:
        # Fall back to local storage
        local_path = _local_media_dir() / filename
        local_path.write_bytes(data)
        result["permanent_url"] = f"/media/{filename}"
        result["stored"] = "local"
        logger.info("Media stored locally: %s (%d bytes)", local_path, len(data))

    return result


async def _download_media(url: str, auth: tuple | None = None) -> bytes | None:
    """Download media file from URL with optional HTTP Basic Auth."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"User-Agent": "SMS-Andon-System/1.0"}
            if auth:
                response = await client.get(url, headers=headers, auth=auth)
            else:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content
    except Exception as exc:
        logger.warning("Media download failed for %s: %s", url, exc)
        return None


async def _store_to_s3(data: bytes, filename: str, content_type: str) -> str | None:
    """Upload to S3 and return the public URL, or None on failure."""
    if not all([settings.s3_bucket, settings.s3_access_key_id, settings.s3_secret_access_key]):
        return None

    try:
        import boto3
        from botocore.exceptions import ClientError

        session = boto3.Session(
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region or "us-east-1",
        )
        s3 = session.client("s3")

        key = f"andon/media/{filename}"
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        # Return the S3 object URL
        region = settings.s3_region or "us-east-1"
        url = f"https://{settings.s3_bucket}.s3.{region}.amazonaws.com/{key}"
        logger.info("Media uploaded to S3: %s", url)
        return url

    except ImportError:
        logger.warning("boto3 not installed — skipping S3 upload.")
        return None
    except Exception as exc:
        logger.warning("S3 upload failed: %s", exc)
        return None
