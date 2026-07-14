from __future__ import annotations

import datetime as dt
import socket
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import quote, urlsplit, urlunsplit

import requests

from .config import Settings


WEBHOOK_USER_AGENT = "pi-camera-sentinel"


def validate_webhook_url(url: str) -> str:
    if not url:
        raise ValueError("Home Assistant webhook URL is not configured")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Home Assistant webhook URL must use http or https")
    if parts.fragment:
        raise ValueError("Home Assistant webhook URL cannot contain a fragment")
    return url


def event_capture_url(feed_url: str, capture_name: str | None) -> str | None:
    if not feed_url or not capture_name:
        return None
    parts = urlsplit(feed_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            f"/events/{quote(capture_name)}",
            "",
            "",
        )
    )


def webhook_payload(
    settings: Settings,
    *,
    event: str,
    captured_at: dt.datetime,
    ratio: float | None = None,
    capture_path: Path | None = None,
    batch_count: int | None = None,
    batch_duration_seconds: float | None = None,
    batch_capture_paths: Sequence[Path] | None = None,
) -> dict[str, object]:
    if captured_at.tzinfo is None:
        captured_at = captured_at.astimezone()
    capture_name = capture_path.name if capture_path is not None else None
    payload: dict[str, object] = {
        "event": event,
        "source": "pi-camera-sentinel",
        "camera": settings.dashboard_title,
        "hostname": socket.gethostname(),
        "captured_at": captured_at.isoformat(),
        "changed_ratio": round(ratio, 6) if ratio is not None else None,
        "capture": capture_name,
        "event_url": event_capture_url(settings.feed_url, capture_name),
        "feed_url": settings.feed_url or None,
    }
    if batch_count is not None:
        capture_names = [path.name for path in batch_capture_paths or ()]
        payload["batch"] = {
            "detection_count": batch_count,
            "duration_seconds": round(batch_duration_seconds or 0.0, 3),
            "photo_count": len(capture_names),
            "captures": capture_names,
            "event_urls": [event_capture_url(settings.feed_url, name) for name in capture_names],
        }
    return payload


def deliver_webhook(
    settings: Settings,
    payload: dict[str, object],
    *,
    post: Callable[..., requests.Response] = requests.post,
) -> int:
    url = validate_webhook_url(settings.webhook_url)
    if settings.webhook_timeout <= 0:
        raise ValueError("webhook timeout must be greater than zero")
    response = post(
        url,
        json=payload,
        timeout=settings.webhook_timeout,
        headers={"User-Agent": WEBHOOK_USER_AGENT},
    )
    response.raise_for_status()
    return response.status_code
