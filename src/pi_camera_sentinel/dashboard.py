from __future__ import annotations

import datetime as dt
import gzip
import io
import json
import logging
import math
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from email.utils import formatdate
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunsplit

import requests
from PIL import Image, ImageStat

from . import __version__
from .camera import apply_profile, camera_state, set_controls
from .config import Settings
from .health import PowerStatus, disk_status, read_cpu_temperature, read_power_status
from .health_alerts import HealthAlertState, load_health_alert_state
from .masks import MAX_MOTION_MASKS, load_motion_masks, save_motion_masks, validate_motion_masks
from .policy import AlertPolicy, load_alert_policy, save_alert_policy
from .recovery import RecoveryState, load_recovery_state, manual_restart_feed
from .retention import (
    ArchiveFile,
    RetentionPolicy,
    archive_files,
    plan_retention,
    policy_from_settings,
)
from .services import service_states, set_service_active
from .webhook import deliver_webhook, webhook_payload


LOG = logging.getLogger("pi-camera-sentinel.dashboard")
STATIC_DIR = Path(__file__).with_name("static")
PROXY_HEADERS = {
    "cache-control",
    "content-length",
    "content-type",
    "expires",
    "pragma",
}
EVENT_WINDOWS = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "all": None,
}
MAX_EVENT_PAGE_SIZE = 48
MAX_ACTIVITY_BUCKETS = 14
EVENT_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
EVENT_THUMBNAIL_SIZE = (480, 270)
EVENT_THUMBNAIL_QUALITY = 72
IMMUTABLE_CACHE_SECONDS = 365 * 24 * 60 * 60
SERVICE_STATUS_CACHE_SECONDS = 5.0
LUMA_SAMPLE_SECONDS = 30.0
MIN_GZIP_BYTES = 1024


def read_system_uptime() -> float | None:
    try:
        value = Path("/proc/uptime").read_text(encoding="ascii").split()[0]
        return round(float(value), 1)
    except (OSError, ValueError, IndexError):
        return None


def frame_luma(image: Image.Image) -> float:
    image.draft("L", (320, 180))
    image.load()
    sample = image if image.mode == "L" else image.convert("L")
    if sample.width > 320 or sample.height > 180:
        sample.thumbnail((320, 180), Image.Resampling.BILINEAR)
    return round(ImageStat.Stat(sample).mean[0], 1)


@lru_cache(maxsize=256)
def event_thumbnail_bytes(path_text: str, _modified_ns: int, _size_bytes: int) -> bytes:
    with Image.open(path_text) as image:
        image.draft("RGB", EVENT_THUMBNAIL_SIZE)
        image.load()
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.thumbnail(EVENT_THUMBNAIL_SIZE, Image.Resampling.BILINEAR)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=EVENT_THUMBNAIL_QUALITY)
        return output.getvalue()


def directory_signature(directory: Path) -> tuple[int, int] | None:
    try:
        stat = directory.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_ctime_ns


def positive_header_int(headers: object, name: str) -> int | None:
    try:
        value = int(getattr(headers, "get")(name, ""))
    except (AttributeError, TypeError, ValueError):
        return None
    return value if value > 0 else None


def collect_dashboard_status(
    settings: Settings,
    *,
    power_status: PowerStatus,
    snapshot_get: Callable[..., requests.Response] = requests.get,
    cached_frame_metrics: tuple[int, int, float] | None = None,
    sample_luma: bool = True,
) -> dict:
    started = time.monotonic()
    feed: dict[str, object] = {
        "ok": False,
        "online": False,
        "status_code": None,
        "content_type": "",
        "width": None,
        "height": None,
        "frame_timestamp": None,
        "frame_age_seconds": None,
        "stale": False,
        "latency_ms": None,
        "dropped_frames": None,
        "mean_luma": None,
        "error": None,
    }
    warnings: list[str] = []

    try:
        response = snapshot_get(settings.snapshot_url, timeout=settings.http_timeout)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        cached_width, cached_height, cached_luma = cached_frame_metrics or (None, None, None)
        width = positive_header_int(response.headers, "x-ustreamer-width") or cached_width
        height = positive_header_int(response.headers, "x-ustreamer-height") or cached_height
        mean_luma = cached_luma
        if sample_luma or width is None or height is None:
            with Image.open(io.BytesIO(response.content)) as image:
                width, height = image.size
                if sample_luma or mean_luma is None:
                    mean_luma = frame_luma(image)
        timestamp = response.headers.get("x-timestamp")
        frame_timestamp = float(timestamp) if timestamp else None
        frame_age_seconds = (
            round(max(0.0, time.time() - frame_timestamp), 2)
            if frame_timestamp is not None
            else None
        )
        dropped = response.headers.get("x-ustreamer-dropped")
        feed.update(
            {
                "ok": content_type.startswith("image/"),
                "online": response.headers.get("x-ustreamer-online", "true").lower() == "true",
                "status_code": response.status_code,
                "content_type": content_type,
                "width": width,
                "height": height,
                "frame_timestamp": frame_timestamp,
                "frame_age_seconds": frame_age_seconds,
                "stale": bool(
                    frame_age_seconds is not None
                    and frame_age_seconds > settings.recovery_stale_seconds
                ),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "dropped_frames": int(dropped) if dropped is not None else None,
                "mean_luma": mean_luma,
            }
        )
    except (requests.RequestException, OSError, ValueError) as exc:
        feed["latency_ms"] = round((time.monotonic() - started) * 1000)
        feed["error"] = str(exc)
        warnings.append("camera snapshot is unavailable")

    if feed["stale"]:
        warnings.append(
            f"camera frame is older than {settings.recovery_stale_seconds:g} seconds"
        )

    camera_exists = settings.camera_device == "auto" or Path(settings.camera_device).exists()
    if not camera_exists:
        warnings.append(f"camera device not found: {settings.camera_device}")

    disk_path, disk_free_bytes, disk_total_bytes, disk_low = disk_status(
        settings.output_dir,
        settings.disk_min_free_mb,
    )
    if disk_low:
        warnings.append(f"less than {settings.disk_min_free_mb} MB of storage remains")
    if power_status.state == "active":
        warnings.append(f"active Pi power limit: {', '.join(power_status.current_issues)}")
    elif power_status.state == "recovered":
        warnings.append("recent Pi undervoltage recovered; monitor the power supply")
    elif power_status.state == "recent":
        warnings.append("recent Pi kernel logs report undervoltage; current hardware state is unavailable")

    try:
        recovery_state = load_recovery_state(
            settings.recovery_state_file,
            stream_service=settings.stream_service,
        )
    except (OSError, ValueError):
        recovery_state = RecoveryState(
            status="unavailable",
            stream_service=settings.stream_service,
            last_reason="Recovery state is unreadable",
        )
        warnings.append("feed recovery state is unreadable")

    try:
        health_alert_state = load_health_alert_state(settings.health_state_file)
    except (OSError, ValueError):
        health_alert_state = HealthAlertState()
        warnings.append("system health alert state is unreadable")

    feed_ok = bool(feed["ok"] and feed["online"] and not feed["stale"])
    if not feed_ok or not camera_exists:
        state = "offline"
    elif disk_low or power_status.state in {"active", "recovered", "recent"}:
        state = "degraded"
    else:
        state = "online"

    return {
        "version": __version__,
        "title": settings.dashboard_title,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "state": state,
        "ok": feed_ok and camera_exists and not disk_low,
        "feed": feed,
        "camera": {
            "device": settings.camera_device,
            "exists": camera_exists,
        },
        "automation": {
            "alert_batching": {
                "enabled": settings.alert_batch_seconds > 0,
                "window_seconds": settings.alert_batch_seconds,
                "max_photos": settings.alert_batch_max_photos,
            },
            "feed_recovery": {
                "interval_seconds": settings.recovery_interval_seconds,
                "failure_threshold": settings.recovery_failure_threshold,
                "stale_seconds": settings.recovery_stale_seconds,
                "cooldown_seconds": settings.recovery_cooldown_seconds,
                "telegram_alerts": (
                    settings.recovery_telegram_alerts
                    and not settings.missing_telegram_fields()
                ),
                "state": recovery_state.to_dict(),
            },
            "health_alerts": {
                "interval_seconds": settings.health_interval_seconds,
                "failure_threshold": settings.health_failure_threshold,
                "recovery_threshold": settings.health_recovery_threshold,
                "temperature_max_c": settings.health_temperature_max_c,
                "telegram_alerts": (
                    settings.health_telegram_alerts
                    and not settings.missing_telegram_fields()
                ),
                "state": health_alert_state.to_dict(),
            },
        },
        "system": {
            "hostname": socket.gethostname(),
            "uptime_seconds": read_system_uptime(),
            "temperature_c": read_cpu_temperature(),
            "undervoltage_seen": power_status.undervoltage_seen,
            "power": power_status.to_dict(),
            "disk_path": str(disk_path),
            "disk_free_bytes": disk_free_bytes,
            "disk_total_bytes": disk_total_bytes,
            "disk_free_percent": round((disk_free_bytes / disk_total_bytes) * 100, 1),
            "disk_low": disk_low,
        },
        "integrations": {
            "home_assistant": {
                "configured": bool(settings.webhook_url),
            }
        },
        "warnings": warnings,
    }


def motion_event_records(directory: Path) -> list[tuple[Path, float, int]]:
    return [
        (file.path, file.modified_at, file.size_bytes)
        for file in archive_files(directory)
        if file.path.suffix.lower() in EVENT_IMAGE_SUFFIXES
    ]


def event_activity(
    records: list[tuple[Path, float, int]],
    *,
    window: str,
    now: float,
) -> dict[str, object]:
    if window == "24h":
        bucket_count = 24
        bucket_seconds = 60 * 60
    elif window == "7d":
        bucket_count = 7
        bucket_seconds = 24 * 60 * 60
    elif window == "all":
        if records:
            span_seconds = max(1.0, now - records[-1][1])
            days_per_bucket = max(
                1,
                math.ceil(span_seconds / (MAX_ACTIVITY_BUCKETS * 24 * 60 * 60)),
            )
            bucket_seconds = days_per_bucket * 24 * 60 * 60
            bucket_count = min(
                MAX_ACTIVITY_BUCKETS,
                max(1, math.ceil(span_seconds / bucket_seconds)),
            )
        else:
            bucket_count = 1
            bucket_seconds = 24 * 60 * 60
    else:
        raise ValueError("window must be one of: 24h, 7d, all")

    started_at = now - (bucket_count * bucket_seconds)
    buckets = [
        {
            "started_at": dt.datetime.fromtimestamp(
                started_at + (index * bucket_seconds),
                dt.timezone.utc,
            ).isoformat(),
            "ended_at": dt.datetime.fromtimestamp(
                started_at + ((index + 1) * bucket_seconds),
                dt.timezone.utc,
            ).isoformat(),
            "count": 0,
            "size_bytes": 0,
        }
        for index in range(bucket_count)
    ]
    for _path, timestamp, size in records:
        index = math.floor((timestamp - started_at) / bucket_seconds)
        index = min(max(index, 0), bucket_count - 1)
        buckets[index]["count"] += 1
        buckets[index]["size_bytes"] += size

    peak_count = max((bucket["count"] for bucket in buckets), default=0)
    peak_index = max(
        (index for index, bucket in enumerate(buckets) if bucket["count"] == peak_count),
        default=0,
    )
    return {
        "starts_at": dt.datetime.fromtimestamp(started_at, dt.timezone.utc).isoformat(),
        "ends_at": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
        "bucket_seconds": bucket_seconds,
        "active_bucket_count": sum(1 for bucket in buckets if bucket["count"] > 0),
        "peak_count": peak_count,
        "peak_started_at": buckets[peak_index]["started_at"] if peak_count else None,
        "last_captured_at": (
            dt.datetime.fromtimestamp(records[0][1], dt.timezone.utc).isoformat()
            if records
            else None
        ),
        "buckets": buckets,
    }


def event_history(
    directory: Path,
    *,
    window: str = "24h",
    limit: int = 12,
    before: float | None = None,
    period_start: float | None = None,
    period_end: float | None = None,
    now: float | None = None,
    retention_policy: RetentionPolicy | None = None,
    archive: tuple[ArchiveFile, ...] | None = None,
) -> dict[str, object]:
    if window not in EVENT_WINDOWS:
        raise ValueError("window must be one of: 24h, 7d, all")
    if limit < 1 or limit > MAX_EVENT_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_EVENT_PAGE_SIZE}")
    if before is not None and (not math.isfinite(before) or before <= 0):
        raise ValueError("before must be a positive timestamp")
    if (period_start is None) != (period_end is None):
        raise ValueError("period_start and period_end must be provided together")
    if period_start is not None and period_end is not None:
        if (
            not math.isfinite(period_start)
            or not math.isfinite(period_end)
            or period_start <= 0
            or period_end <= 0
        ):
            raise ValueError("period boundaries must be positive timestamps")
        if period_start >= period_end:
            raise ValueError("period_start must be earlier than period_end")

    archive_snapshot = archive_files(directory) if archive is None else archive
    records = [
        (file.path, file.modified_at, file.size_bytes)
        for file in archive_snapshot
        if file.path.suffix.lower() in EVENT_IMAGE_SUFFIXES
    ]
    current_time = time.time() if now is None else now
    window_seconds = EVENT_WINDOWS[window]
    cutoff = current_time - window_seconds if window_seconds is not None else None
    window_records = [record for record in records if cutoff is None or record[1] >= cutoff]
    selected_records = window_records
    selection = None
    if period_start is not None and period_end is not None:
        selected_records = [
            record
            for record in window_records
            if period_start <= record[1] < period_end
        ]
        selection = {
            "started_at": dt.datetime.fromtimestamp(period_start, dt.timezone.utc).isoformat(),
            "ended_at": dt.datetime.fromtimestamp(period_end, dt.timezone.utc).isoformat(),
            "count": len(selected_records),
            "size_bytes": sum(record[2] for record in selected_records),
        }
    candidates = [record for record in selected_records if before is None or record[1] < before]
    page = candidates[:limit]
    has_more = len(candidates) > limit
    events = [
        {
            "name": path.name,
            "url": f"/events/{quote(path.name)}",
            "thumbnail_url": (
                f"/events/thumbnails/{quote(path.name)}"
                f"?v={int(timestamp * 1000)}-{size}"
            ),
            "captured_at": dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat(),
            "size_bytes": size,
        }
        for path, timestamp, size in page
    ]

    summary: dict[str, object] = {
        "window_count": len(window_records),
        "window_size_bytes": sum(record[2] for record in window_records),
        "retained_count": len(records),
        "retained_size_bytes": sum(record[2] for record in records),
        "last_captured_at": (
            dt.datetime.fromtimestamp(records[0][1], dt.timezone.utc).isoformat()
            if records
            else None
        ),
    }
    if retention_policy is not None:
        summary["retention"] = plan_retention(
            directory,
            retention_policy,
            now=current_time,
            files=archive_snapshot,
        ).to_dict()

    return {
        "events": events,
        "window": window,
        "summary": summary,
        "activity": event_activity(window_records, window=window, now=current_time),
        "selection": selection,
        "next_before": page[-1][1] if has_more and page else None,
    }


def list_recent_events(directory: Path, limit: int = 12) -> list[dict[str, object]]:
    if limit <= 0:
        return []
    return event_history(directory, window="all", limit=limit)["events"]  # type: ignore[return-value]


def parse_event_query(
    query: str,
) -> tuple[str, int, float | None, float | None, float | None]:
    parameters = parse_qs(query, keep_blank_values=True)
    window = parameters.get("window", ["24h"])[0]
    try:
        limit = int(parameters.get("limit", ["12"])[0])
    except ValueError as exc:
        raise ValueError("limit must be an integer") from exc
    before_text = parameters.get("before", [""])[0]
    try:
        before = float(before_text) if before_text else None
    except ValueError as exc:
        raise ValueError("before must be a timestamp") from exc
    period_start_text = parameters.get("period_start", [""])[0]
    period_end_text = parameters.get("period_end", [""])[0]
    try:
        period_start = float(period_start_text) if period_start_text else None
        period_end = float(period_end_text) if period_end_text else None
    except ValueError as exc:
        raise ValueError("period boundaries must be timestamps") from exc
    if window not in EVENT_WINDOWS:
        raise ValueError("window must be one of: 24h, 7d, all")
    if limit < 1 or limit > MAX_EVENT_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_EVENT_PAGE_SIZE}")
    if before is not None and (not math.isfinite(before) or before <= 0):
        raise ValueError("before must be a positive timestamp")
    if (period_start is None) != (period_end is None):
        raise ValueError("period_start and period_end must be provided together")
    if period_start is not None and period_end is not None:
        if (
            not math.isfinite(period_start)
            or not math.isfinite(period_end)
            or period_start <= 0
            or period_end <= 0
        ):
            raise ValueError("period boundaries must be positive timestamps")
        if period_start >= period_end:
            raise ValueError("period_start must be earlier than period_end")
    return window, limit, before, period_start, period_end


def with_query(url: str, query: str) -> str:
    if not query:
        return url
    parts = urlsplit(url)
    combined = "&".join(value for value in (parts.query, query) if value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, combined, parts.fragment))


def same_origin(origin: str | None, host: str | None) -> bool:
    if not origin:
        return True
    if not host or origin == "null":
        return False
    try:
        return urlsplit(origin).netloc.lower() == host.lower()
    except ValueError:
        return False


def accepts_gzip(value: str | None) -> bool:
    if not value:
        return False
    qualities: dict[str, float] = {}
    for item in value.split(","):
        parts = [part.strip() for part in item.split(";")]
        encoding = parts[0].lower()
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.lower().startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        qualities[encoding] = quality
    if "gzip" in qualities:
        return qualities["gzip"] > 0
    return qualities.get("*", 0.0) > 0


def compressible_content_type(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith("text/") or media_type in {
        "application/javascript",
        "application/json",
        "application/xml",
        "image/svg+xml",
    }


def file_etag(stat: os.stat_result, variant: str = "") -> str:
    modified_ns = stat.st_mtime_ns
    size = stat.st_size
    suffix = f"-{variant}" if variant else ""
    return f'"{modified_ns:x}-{size:x}{suffix}"'


def encoded_etag(etag: str, encoding: str | None) -> str:
    if not encoding:
        return etag
    return f'{etag[:-1]}-{encoding}"'


class DashboardApplication:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._status: dict | None = None
        self._status_at = 0.0
        self._power: PowerStatus | None = None
        self._power_at = 0.0
        self._frame_metrics: tuple[int, int, float] | None = None
        self._frame_metrics_at = 0.0
        self._archive_cache_ready = False
        self._archive_files: tuple[ArchiveFile, ...] = ()
        self._archive_signature: tuple[int, int] | None = None
        self._services: dict[str, dict[str, object]] | None = None
        self._services_at = 0.0
        self._camera_lock = threading.RLock()
        self._event_lock = threading.RLock()
        self._mask_lock = threading.RLock()
        self._policy_lock = threading.RLock()
        self._recovery_lock = threading.RLock()
        self._service_lock = threading.RLock()
        self._status_lock = threading.RLock()

    def status(self) -> dict:
        with self._status_lock:
            now = time.monotonic()
            if self._status is not None and now - self._status_at < self.settings.dashboard_status_cache_seconds:
                return self._status
            if self._power is None or now - self._power_at >= 60:
                self._power = read_power_status()
                self._power_at = now
            sample_luma = (
                self._frame_metrics is None
                or now - self._frame_metrics_at >= LUMA_SAMPLE_SECONDS
            )
            self._status = collect_dashboard_status(
                self.settings,
                power_status=self._power,
                cached_frame_metrics=self._frame_metrics,
                sample_luma=sample_luma,
            )
            feed = self._status["feed"]
            if feed["ok"] and all(
                isinstance(feed[key], (int, float))
                for key in ("width", "height", "mean_luma")
            ):
                self._frame_metrics = (
                    int(feed["width"]),
                    int(feed["height"]),
                    float(feed["mean_luma"]),
                )
                if sample_luma:
                    self._frame_metrics_at = now
            self._status_at = now
            return self._status

    def archive_snapshot(self) -> tuple[ArchiveFile, ...]:
        signature = directory_signature(self.settings.output_dir)
        with self._event_lock:
            if self._archive_cache_ready and signature == self._archive_signature:
                return self._archive_files
            files = archive_files(self.settings.output_dir)
            refreshed_signature = directory_signature(self.settings.output_dir)
            if refreshed_signature != signature:
                files = archive_files(self.settings.output_dir)
                refreshed_signature = directory_signature(self.settings.output_dir)
            self._archive_files = files
            self._archive_signature = refreshed_signature
            self._archive_cache_ready = True
            return files

    def events(
        self,
        *,
        window: str,
        limit: int,
        before: float | None,
        period_start: float | None,
        period_end: float | None,
    ) -> dict[str, object]:
        return event_history(
            self.settings.output_dir,
            window=window,
            limit=limit,
            before=before,
            period_start=period_start,
            period_end=period_end,
            retention_policy=policy_from_settings(self.settings),
            archive=self.archive_snapshot(),
        )

    def camera(self) -> dict[str, object]:
        with self._camera_lock:
            return camera_state(self.settings.camera_device)

    def apply_camera_profile(self, profile: str) -> dict[str, object]:
        with self._camera_lock:
            apply_profile(self.settings.camera_device, profile)
            return camera_state(self.settings.camera_device)

    def update_camera_controls(self, values: dict[str, int]) -> dict[str, object]:
        with self._camera_lock:
            return set_controls(self.settings.camera_device, values)

    def alert_policy(self) -> dict[str, object]:
        with self._policy_lock:
            policy = load_alert_policy(self.settings.policy_file)
            return policy.to_dict(self.settings.timezone)

    def update_alert_policy(self, payload: dict) -> dict[str, object]:
        with self._policy_lock:
            policy = AlertPolicy.from_dict(payload)
            state = policy.to_dict(self.settings.timezone)
            save_alert_policy(self.settings.policy_file, policy)
            return state

    def motion_masks(self) -> dict[str, object]:
        with self._mask_lock:
            masks = load_motion_masks(self.settings.mask_file)
            return {
                "regions": [mask.to_dict() for mask in masks],
                "max_regions": MAX_MOTION_MASKS,
            }

    def update_motion_masks(self, payload: dict) -> dict[str, object]:
        with self._mask_lock:
            masks = validate_motion_masks(payload.get("regions"))
            save_motion_masks(self.settings.mask_file, masks)
            return {
                "regions": [mask.to_dict() for mask in masks],
                "max_regions": MAX_MOTION_MASKS,
            }

    def send_webhook_test(self) -> dict[str, object]:
        status_code = deliver_webhook(
            self.settings,
            webhook_payload(
                self.settings,
                event="test",
                captured_at=dt.datetime.now().astimezone(),
            ),
        )
        return {
            "configured": True,
            "delivered": True,
            "status_code": status_code,
        }

    def restart_feed(self) -> dict[str, object]:
        with self._recovery_lock:
            state = load_recovery_state(
                self.settings.recovery_state_file,
                stream_service=self.settings.stream_service,
            )
            try:
                updated = manual_restart_feed(self.settings, state)
            finally:
                with self._status_lock:
                    self._status = None
                    self._status_at = 0.0
            return updated.to_dict()

    def services(self) -> dict[str, dict[str, object]]:
        with self._service_lock:
            now = time.monotonic()
            if self._services is not None and now - self._services_at < SERVICE_STATUS_CACHE_SECONDS:
                return self._services
            names = {
                "motion": self.settings.motion_service,
                "recovery": self.settings.recovery_service,
                "health": self.settings.health_service,
                "watchdog": self.settings.exposure_service,
            }
            states = service_states(names.values())
            self._services = {service_id: states[name] for service_id, name in names.items()}
            self._services_at = time.monotonic()
            return self._services

    def update_service(self, service_id: str, active: bool) -> dict[str, object]:
        service_names = {
            "motion": self.settings.motion_service,
            "recovery": self.settings.recovery_service,
            "health": self.settings.health_service,
            "watchdog": self.settings.exposure_service,
        }
        try:
            service_name = service_names[service_id]
        except KeyError as exc:
            raise ValueError("unknown service") from exc
        with self._service_lock:
            state = set_service_active(service_name, active)
            self._services = None
            self._services_at = 0.0
            return state


class DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], app: DashboardApplication):
        self.app = app
        super().__init__(server_address, DashboardRequestHandler)

    def handle_error(self, request: object, client_address: tuple[str, int]) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            LOG.debug("dashboard client %s disconnected", client_address[0])
            return
        super().handle_error(request, client_address)


class DashboardRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = f"PiCameraSentinel/{__version__}"

    @property
    def app(self) -> DashboardApplication:
        return self.server.app  # type: ignore[attr-defined, no-any-return]

    def log_message(self, format_string: str, *args: object) -> None:
        LOG.debug("%s - %s", self.client_address[0], format_string % args)

    def end_headers(self) -> None:
        started_at = getattr(self, "_request_started_at", None)
        if started_at is not None:
            duration_ms = (time.perf_counter() - started_at) * 1000
            self.send_header("Server-Timing", f"app;dur={duration_ms:.1f}")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def send_bytes(
        self,
        status: HTTPStatus,
        content_type: str,
        body: bytes,
        *,
        cache_control: str = "no-store",
        content_disposition: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        vary_encoding = compressible_content_type(content_type)
        use_gzip = (
            vary_encoding
            and len(body) >= MIN_GZIP_BYTES
            and accepts_gzip(self.headers.get("Accept-Encoding"))
        )
        content_encoding = "gzip" if use_gzip else None
        response_etag = encoded_etag(etag, content_encoding) if etag else None
        if response_etag and self.request_etag_matches(response_etag):
            self.send_response(HTTPStatus.NOT_MODIFIED)
            self.send_header("Cache-Control", cache_control)
            self.send_header("ETag", response_etag)
            if last_modified:
                self.send_header("Last-Modified", last_modified)
            if vary_encoding:
                self.send_header("Vary", "Accept-Encoding")
            if content_encoding:
                self.send_header("Content-Encoding", content_encoding)
            self.end_headers()
            return

        if use_gzip:
            body = gzip.compress(body, compresslevel=5, mtime=0)

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        if response_etag:
            self.send_header("ETag", response_etag)
        if last_modified:
            self.send_header("Last-Modified", last_modified)
        if vary_encoding:
            self.send_header("Vary", "Accept-Encoding")
        if content_encoding:
            self.send_header("Content-Encoding", content_encoding)
        if content_disposition:
            self.send_header("Content-Disposition", content_disposition)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_bytes(status, "application/json; charset=utf-8", body)

    def request_etag_matches(self, etag: str) -> bool:
        candidates = {
            candidate.strip()
            for candidate in self.headers.get("If-None-Match", "").split(",")
        }
        return "*" in candidates or etag in candidates

    def send_file(
        self,
        target: Path,
        content_type: str,
        *,
        cache_control: str,
        etag_variant: str = "",
    ) -> None:
        try:
            stat = target.stat()
        except OSError:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        etag = file_etag(stat, etag_variant)
        last_modified = formatdate(stat.st_mtime, usegmt=True)
        if self.request_etag_matches(etag):
            self.send_response(HTTPStatus.NOT_MODIFIED)
            self.send_header("Cache-Control", cache_control)
            self.send_header("ETag", etag)
            self.send_header("Last-Modified", last_modified)
            self.end_headers()
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header("Cache-Control", cache_control)
        self.send_header("ETag", etag)
        self.send_header("Last-Modified", last_modified)
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            with target.open("rb") as source:
                shutil.copyfileobj(source, self.wfile, length=64 * 1024)
        except FileNotFoundError:
            return

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        self._request_started_at = time.perf_counter()
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/":
            self.serve_static("index.html")
        elif path.startswith("/assets/"):
            self.serve_static(path.removeprefix("/assets/"))
        elif path == "/api/status":
            self.send_json(self.app.status())
        elif path == "/api/events":
            try:
                window, limit, before, period_start, period_end = parse_event_query(parsed.query)
                self.send_json(
                    self.app.events(
                        window=window,
                        limit=limit,
                        before=before,
                        period_start=period_start,
                        period_end=period_end,
                    )
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        elif path == "/api/camera":
            self.send_camera_state()
        elif path == "/api/policy":
            self.send_policy_state()
        elif path == "/api/masks":
            self.send_motion_masks_state()
        elif path == "/api/services":
            self.send_json({"services": self.app.services()})
        elif path == "/healthz":
            payload = self.app.status()
            status = HTTPStatus.OK if payload["ok"] else HTTPStatus.SERVICE_UNAVAILABLE
            self.send_json(payload, status)
        elif path == "/stream":
            self.proxy_stream(parsed.query)
        elif path == "/snapshot":
            download = parse_qs(parsed.query).get("download") == ["1"]
            self.proxy_snapshot(parsed.query, download=download)
        elif path.startswith("/events/thumbnails/"):
            self.serve_event_thumbnail(unquote(path.removeprefix("/events/thumbnails/")))
        elif path.startswith("/events/"):
            self.serve_event(unquote(path.removeprefix("/events/")))
        else:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        self._request_started_at = time.perf_counter()
        if not same_origin(self.headers.get("Origin"), self.headers.get("Host")):
            self.send_json({"error": "cross-origin changes are not allowed"}, HTTPStatus.FORBIDDEN)
            return
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        path = urlsplit(self.path).path
        if path == "/api/camera/profile":
            profile = payload.get("profile")
            if not isinstance(profile, str):
                self.send_json({"error": "profile must be a string"}, HTTPStatus.BAD_REQUEST)
                return
            self.run_camera_action(lambda: self.app.apply_camera_profile(profile))
        elif path == "/api/camera/controls":
            controls = payload.get("controls")
            if not isinstance(controls, dict):
                self.send_json({"error": "controls must be an object"}, HTTPStatus.BAD_REQUEST)
                return
            self.run_camera_action(lambda: self.app.update_camera_controls(controls))
        elif path == "/api/policy":
            self.run_policy_action(lambda: self.app.update_alert_policy(payload))
        elif path == "/api/masks":
            self.run_motion_masks_action(lambda: self.app.update_motion_masks(payload))
        elif path == "/api/webhook/test":
            self.run_webhook_action(self.app.send_webhook_test)
        elif path == "/api/recovery/restart":
            self.run_recovery_action(self.app.restart_feed)
        elif path.startswith("/api/services/"):
            service_id = path.removeprefix("/api/services/")
            active = payload.get("active")
            if not isinstance(active, bool):
                self.send_json({"error": "active must be a boolean"}, HTTPStatus.BAD_REQUEST)
                return
            self.run_service_action(lambda: self.app.update_service(service_id, active))
        else:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def read_json_body(self) -> dict:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("request content type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length <= 0 or length > 8192:
            raise ValueError("request body must be between 1 and 8192 bytes")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def send_camera_state(self) -> None:
        self.run_camera_action(self.app.camera)

    def send_policy_state(self) -> None:
        try:
            self.send_json(self.app.alert_policy())
        except (OSError, ValueError) as exc:
            LOG.warning("alert policy read failed: %s", exc)
            self.send_json({"error": "alert policy is unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def send_motion_masks_state(self) -> None:
        try:
            self.send_json(self.app.motion_masks())
        except (OSError, ValueError) as exc:
            LOG.warning("motion mask read failed: %s", exc)
            self.send_json({"error": "motion masks are unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_camera_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, subprocess.SubprocessError) as exc:
            LOG.warning("camera control action failed: %s", exc)
            self.send_json({"error": "camera controls are unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_service_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, subprocess.SubprocessError) as exc:
            LOG.warning("service control action failed: %s", exc)
            self.send_json({"error": "service control is unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_policy_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            LOG.warning("alert policy write failed: %s", exc)
            self.send_json({"error": "alert policy is unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_motion_masks_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            LOG.warning("motion mask write failed: %s", exc)
            self.send_json({"error": "motion masks are unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_webhook_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except requests.RequestException as exc:
            LOG.warning("Home Assistant webhook test failed: %s", exc)
            self.send_json({"error": "Home Assistant webhook delivery failed"}, HTTPStatus.BAD_GATEWAY)

    def run_recovery_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, subprocess.SubprocessError) as exc:
            LOG.warning("manual feed recovery failed: %s", exc)
            self.send_json({"error": "feed restart is unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def serve_static(self, name: str) -> None:
        target = (STATIC_DIR / name).resolve()
        if target.parent != STATIC_DIR.resolve() or not target.is_file():
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            stat = target.stat()
            body = target.read_bytes()
        except OSError:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_bytes(
            HTTPStatus.OK,
            content_type,
            body,
            cache_control=(
                f"public, max-age={IMMUTABLE_CACHE_SECONDS}, immutable"
                if target.name != "index.html"
                else "no-cache"
            ),
            etag=file_etag(stat),
            last_modified=formatdate(stat.st_mtime, usegmt=True),
        )

    def event_target(self, name: str) -> Path | None:
        directory = self.app.settings.output_dir.resolve()
        target = (directory / name).resolve()
        if target.parent != directory or not target.is_file() or not target.name.startswith("motion-"):
            return None
        return target

    def serve_event(self, name: str) -> None:
        target = self.event_target(name)
        if target is None:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_file(
            target,
            content_type,
            cache_control=f"private, max-age={IMMUTABLE_CACHE_SECONDS}, immutable",
        )

    def serve_event_thumbnail(self, name: str) -> None:
        target = self.event_target(name)
        if target is None or target.suffix.lower() not in EVENT_IMAGE_SUFFIXES:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            stat = target.stat()
            body = event_thumbnail_bytes(str(target), stat.st_mtime_ns, stat.st_size)
        except OSError:
            self.send_json({"error": "thumbnail unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self.send_bytes(
            HTTPStatus.OK,
            "image/jpeg",
            body,
            cache_control=f"private, max-age={IMMUTABLE_CACHE_SECONDS}, immutable",
            etag=file_etag(stat, "thumb-v1"),
            last_modified=formatdate(stat.st_mtime, usegmt=True),
        )

    def copy_proxy_headers(self, response: requests.Response) -> None:
        for name, value in response.headers.items():
            if name.lower() in PROXY_HEADERS or name.lower().startswith("x-ustreamer-") or name.lower() == "x-timestamp":
                self.send_header(name, value)

    def proxy_snapshot(self, query: str, *, download: bool) -> None:
        try:
            response = requests.get(
                with_query(self.app.settings.snapshot_url, query),
                timeout=self.app.settings.http_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.send_json({"error": f"snapshot upstream unavailable: {exc}"}, HTTPStatus.BAD_GATEWAY)
            return
        self.send_response(response.status_code)
        self.copy_proxy_headers(response)
        if download:
            stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
            self.send_header("Content-Disposition", f'attachment; filename="sentinel-{stamp}.jpg"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response.content)

    def proxy_stream(self, query: str) -> None:
        response_started = False
        try:
            with requests.get(
                with_query(self.app.settings.stream_url, query),
                stream=True,
                timeout=(self.app.settings.http_timeout, None),
            ) as response:
                response.raise_for_status()
                self.send_response(response.status_code)
                self.copy_proxy_headers(response)
                self.send_header("Connection", "close")
                self.end_headers()
                response_started = True
                if self.command == "HEAD":
                    return
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        self.wfile.write(chunk)
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            LOG.debug("stream client disconnected")
        except requests.RequestException as exc:
            if response_started:
                LOG.debug("stream connection ended: %s", exc)
            else:
                LOG.warning("stream upstream unavailable: %s", exc)
                self.send_json({"error": f"stream upstream unavailable: {exc}"}, HTTPStatus.BAD_GATEWAY)


def serve_dashboard(settings: Settings) -> None:
    app = DashboardApplication(settings)
    server = DashboardHTTPServer((settings.dashboard_host, settings.dashboard_port), app)
    LOG.info(
        "dashboard listening on http://%s:%s with stream upstream %s",
        settings.dashboard_host,
        settings.dashboard_port,
        settings.stream_url,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        LOG.info("stopping dashboard")
    finally:
        server.server_close()
