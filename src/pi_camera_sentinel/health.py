from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from .config import Settings


@dataclass
class HealthResult:
    ok: bool
    snapshot_url: str
    camera_device: str
    snapshot_ok: bool
    snapshot_status: str
    camera_device_exists: bool
    undervoltage_seen: bool | None
    disk_path: str
    disk_free_bytes: int
    disk_total_bytes: int
    disk_low: bool
    notes: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def recent_undervoltage_seen() -> bool | None:
    if not shutil.which("journalctl"):
        return None
    try:
        result = subprocess.run(
            ["journalctl", "-k", "--since", "2 hours ago", "--no-pager"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    text = result.stdout.lower()
    return "undervoltage" in text or "under-voltage" in text


def existing_disk_path(path: Path) -> Path:
    candidate = path.expanduser()
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def disk_status(path: Path, min_free_mb: int) -> tuple[Path, int, int, bool]:
    disk_path = existing_disk_path(path)
    usage = shutil.disk_usage(disk_path)
    low = usage.free < max(min_free_mb, 0) * 1024 * 1024
    return disk_path, usage.free, usage.total, low


def check_health(settings: Settings) -> HealthResult:
    notes: list[str] = []
    snapshot_ok = False
    snapshot_status = "not checked"
    try:
        response = requests.get(settings.snapshot_url, timeout=settings.http_timeout)
        snapshot_ok = response.ok and response.headers.get("content-type", "").startswith("image/")
        snapshot_status = f"HTTP {response.status_code} {response.headers.get('content-type', '')}".strip()
    except requests.RequestException as exc:
        snapshot_status = str(exc)

    camera_device_exists = settings.camera_device == "auto"
    if settings.camera_device != "auto":
        camera_device_exists = Path(settings.camera_device).exists()
        if not camera_device_exists:
            notes.append(f"camera device not found: {settings.camera_device}")

    undervoltage = recent_undervoltage_seen()
    if undervoltage:
        notes.append("recent kernel logs mention undervoltage; check Pi power supply and USB camera power draw")

    disk_path, disk_free_bytes, disk_total_bytes, disk_low = disk_status(
        settings.output_dir,
        settings.disk_min_free_mb,
    )
    if disk_low:
        notes.append(
            f"low disk space at {disk_path}: less than {settings.disk_min_free_mb} MB free"
        )

    ok = snapshot_ok and camera_device_exists and not disk_low
    return HealthResult(
        ok=ok,
        snapshot_url=settings.snapshot_url,
        camera_device=settings.camera_device,
        snapshot_ok=snapshot_ok,
        snapshot_status=snapshot_status,
        camera_device_exists=camera_device_exists,
        undervoltage_seen=undervoltage,
        disk_path=str(disk_path),
        disk_free_bytes=disk_free_bytes,
        disk_total_bytes=disk_total_bytes,
        disk_low=disk_low,
        notes=notes,
    )
