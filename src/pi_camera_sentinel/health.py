from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

from .config import Settings


Runner = Callable[..., subprocess.CompletedProcess[str]]
Which = Callable[[str], Optional[str]]
THROTTLED_PATTERN = re.compile(r"throttled=(0x[0-9a-fA-F]+)")
CURRENT_POWER_FLAGS = {
    0: "Undervoltage",
    1: "Frequency capped",
    2: "CPU throttled",
    3: "Soft temperature limit",
}
OCCURRED_POWER_FLAGS = {
    16: "Undervoltage",
    17: "Frequency capped",
    18: "CPU throttled",
    19: "Soft temperature limit",
}


@dataclass(frozen=True)
class PowerStatus:
    state: str
    available: bool
    raw_value: str | None
    current_issues: tuple[str, ...]
    occurred_issues: tuple[str, ...]
    recent_log_undervoltage: bool | None
    undervoltage_seen: bool | None
    under_voltage_now: bool | None
    frequency_capped_now: bool | None
    throttled_now: bool | None
    soft_temperature_limit_now: bool | None
    under_voltage_occurred: bool | None
    frequency_capped_occurred: bool | None
    throttled_occurred: bool | None
    soft_temperature_limit_occurred: bool | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class HealthResult:
    ok: bool
    snapshot_url: str
    camera_device: str
    snapshot_ok: bool
    snapshot_status: str
    camera_device_exists: bool
    undervoltage_seen: bool | None
    power: PowerStatus
    disk_path: str
    disk_free_bytes: int
    disk_total_bytes: int
    disk_low: bool
    notes: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def recent_undervoltage_seen(
    *,
    which: Which = shutil.which,
    runner: Runner = subprocess.run,
) -> bool | None:
    if not which("journalctl"):
        return None
    try:
        result = runner(
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


def parse_throttled_output(text: str) -> tuple[int, str]:
    match = THROTTLED_PATTERN.fullmatch(text.strip())
    if match is None:
        raise ValueError("invalid vcgencmd throttling response")
    raw_value = match.group(1).lower()
    return int(raw_value, 16), raw_value


def read_throttle_flags(
    *,
    which: Which = shutil.which,
    runner: Runner = subprocess.run,
) -> tuple[int, str] | None:
    if not which("vcgencmd"):
        return None
    try:
        result = runner(
            ["vcgencmd", "get_throttled"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        return parse_throttled_output(result.stdout)
    except ValueError:
        return None


def power_status_from_flags(
    throttle: tuple[int, str] | None,
    recent_log_undervoltage: bool | None,
) -> PowerStatus:
    flags = throttle[0] if throttle is not None else None
    raw_value = throttle[1] if throttle is not None else None
    current_issues = tuple(
        label for bit, label in CURRENT_POWER_FLAGS.items() if flags is not None and flags & (1 << bit)
    )
    occurred_issues = tuple(
        label for bit, label in OCCURRED_POWER_FLAGS.items() if flags is not None and flags & (1 << bit)
    )

    if current_issues:
        state = "active"
    elif flags is not None and recent_log_undervoltage:
        state = "recovered"
    elif flags is None and recent_log_undervoltage:
        state = "recent"
    elif occurred_issues:
        state = "historical"
    elif flags is not None:
        state = "stable"
    else:
        state = "unknown"

    def flag(bit: int) -> bool | None:
        return bool(flags & (1 << bit)) if flags is not None else None

    if flags is not None:
        undervoltage_seen: bool | None = bool(flag(0) or recent_log_undervoltage)
    else:
        undervoltage_seen = recent_log_undervoltage

    return PowerStatus(
        state=state,
        available=flags is not None,
        raw_value=raw_value,
        current_issues=current_issues,
        occurred_issues=occurred_issues,
        recent_log_undervoltage=recent_log_undervoltage,
        undervoltage_seen=undervoltage_seen,
        under_voltage_now=flag(0),
        frequency_capped_now=flag(1),
        throttled_now=flag(2),
        soft_temperature_limit_now=flag(3),
        under_voltage_occurred=flag(16),
        frequency_capped_occurred=flag(17),
        throttled_occurred=flag(18),
        soft_temperature_limit_occurred=flag(19),
    )


def read_power_status() -> PowerStatus:
    return power_status_from_flags(read_throttle_flags(), recent_undervoltage_seen())


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

    power = read_power_status()
    if power.state == "active":
        notes.append(
            f"active Pi power limit: {', '.join(power.current_issues)}; "
            "check the power supply and USB camera power draw"
        )
    elif power.state in {"recovered", "recent"}:
        notes.append("recent Pi kernel logs mention undervoltage; the hardware flag is not active now")
    elif power.state == "historical":
        notes.append(f"Pi power issue occurred since boot: {', '.join(power.occurred_issues)}")

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
        undervoltage_seen=power.undervoltage_seen,
        power=power,
        disk_path=str(disk_path),
        disk_free_bytes=disk_free_bytes,
        disk_total_bytes=disk_total_bytes,
        disk_low=disk_low,
        notes=notes,
    )
