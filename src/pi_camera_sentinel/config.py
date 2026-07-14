from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if not value:
        return default
    return float(value)


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    return int(value)


def env_str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    telegram_chat_id: str
    snapshot_url: str
    stream_url: str
    feed_url: str
    output_dir: Path
    poll_seconds: float
    cooldown_seconds: float
    diff_threshold: int
    changed_ratio: float
    min_motion_frames: int
    resize_width: int
    resize_height: int
    http_timeout: float
    send_photo: bool
    send_video: bool
    video_seconds: int
    video_fps: int
    retention_files: int
    camera_device: str
    exposure_watchdog_interval: float
    exposure_settle_seconds: float
    exposure_dark_mean_max: float
    exposure_dark_ratio_min: float
    exposure_dark_pixel_max: int
    exposure_bright_mean_min: float
    exposure_bright_ratio_min: float
    exposure_bright_pixel_min: int
    exposure_resize_width: int
    exposure_resize_height: int
    exposure_day_profile: str
    exposure_night_profile: str
    disk_min_free_mb: int
    dashboard_host: str
    dashboard_port: int
    dashboard_title: str
    dashboard_status_cache_seconds: float
    motion_service: str
    exposure_service: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            telegram_token=env_str("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=env_str("TELEGRAM_CHAT_ID", ""),
            snapshot_url=env_str("SENTINEL_SNAPSHOT_URL", "http://127.0.0.1:8080/snapshot"),
            stream_url=env_str("SENTINEL_STREAM_URL", "http://127.0.0.1:8080/stream"),
            feed_url=env_str("SENTINEL_FEED_URL", ""),
            output_dir=Path(env_str("SENTINEL_OUTPUT_DIR", "/var/lib/pi-camera-sentinel")),
            poll_seconds=env_float("SENTINEL_POLL_SECONDS", 1.0),
            cooldown_seconds=env_float("SENTINEL_COOLDOWN_SECONDS", 60.0),
            diff_threshold=env_int("SENTINEL_DIFF_THRESHOLD", 25),
            changed_ratio=env_float("SENTINEL_CHANGED_RATIO", 0.035),
            min_motion_frames=env_int("SENTINEL_MIN_FRAMES", 2),
            resize_width=env_int("SENTINEL_RESIZE_WIDTH", 160),
            resize_height=env_int("SENTINEL_RESIZE_HEIGHT", 90),
            http_timeout=env_float("SENTINEL_HTTP_TIMEOUT", 8.0),
            send_photo=env_bool("SENTINEL_SEND_PHOTO", True),
            send_video=env_bool("SENTINEL_SEND_VIDEO", False),
            video_seconds=env_int("SENTINEL_VIDEO_SECONDS", 5),
            video_fps=env_int("SENTINEL_VIDEO_FPS", 10),
            retention_files=env_int("SENTINEL_RETENTION_FILES", 200),
            camera_device=env_str("SENTINEL_CAMERA_DEVICE", "/dev/video0"),
            exposure_watchdog_interval=env_float("SENTINEL_EXPOSURE_WATCHDOG_INTERVAL", 60.0),
            exposure_settle_seconds=env_float("SENTINEL_EXPOSURE_SETTLE_SECONDS", 8.0),
            exposure_dark_mean_max=env_float("SENTINEL_EXPOSURE_DARK_MEAN_MAX", 45.0),
            exposure_dark_ratio_min=env_float("SENTINEL_EXPOSURE_DARK_RATIO_MIN", 0.25),
            exposure_dark_pixel_max=env_int("SENTINEL_EXPOSURE_DARK_PIXEL_MAX", 25),
            exposure_bright_mean_min=env_float("SENTINEL_EXPOSURE_BRIGHT_MEAN_MIN", 230.0),
            exposure_bright_ratio_min=env_float("SENTINEL_EXPOSURE_BRIGHT_RATIO_MIN", 0.85),
            exposure_bright_pixel_min=env_int("SENTINEL_EXPOSURE_BRIGHT_PIXEL_MIN", 180),
            exposure_resize_width=env_int("SENTINEL_EXPOSURE_RESIZE_WIDTH", 160),
            exposure_resize_height=env_int("SENTINEL_EXPOSURE_RESIZE_HEIGHT", 90),
            exposure_day_profile=env_str("SENTINEL_EXPOSURE_DAY_PROFILE", "auto"),
            exposure_night_profile=env_str("SENTINEL_EXPOSURE_NIGHT_PROFILE", "low-light"),
            disk_min_free_mb=env_int("SENTINEL_DISK_MIN_FREE_MB", 512),
            dashboard_host=env_str("SENTINEL_DASHBOARD_HOST", "127.0.0.1"),
            dashboard_port=env_int("SENTINEL_DASHBOARD_PORT", 8090),
            dashboard_title=env_str("SENTINEL_DASHBOARD_TITLE", "Pi Camera Sentinel"),
            dashboard_status_cache_seconds=env_float("SENTINEL_DASHBOARD_STATUS_CACHE_SECONDS", 5.0),
            motion_service=env_str("SENTINEL_MOTION_SERVICE", "pi-camera-motion.service"),
            exposure_service=env_str(
                "SENTINEL_EXPOSURE_SERVICE",
                "pi-camera-exposure-watchdog.service",
            ),
        )

    def missing_telegram_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.telegram_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        return missing
