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
        )

    def missing_telegram_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.telegram_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        return missing
