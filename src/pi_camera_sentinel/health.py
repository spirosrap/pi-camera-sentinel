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

    ok = snapshot_ok and camera_device_exists
    return HealthResult(
        ok=ok,
        snapshot_url=settings.snapshot_url,
        camera_device=settings.camera_device,
        snapshot_ok=snapshot_ok,
        snapshot_status=snapshot_status,
        camera_device_exists=camera_device_exists,
        undervoltage_seen=undervoltage,
        notes=notes,
    )
