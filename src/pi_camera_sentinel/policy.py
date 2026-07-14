from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CLOCK_PATTERN = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]")


def clock_minutes(value: str) -> int:
    if not isinstance(value, str) or not CLOCK_PATTERN.fullmatch(value):
        raise ValueError("quiet-hours times must use 24-hour HH:MM format")
    hours, minutes = value.split(":", 1)
    return int(hours) * 60 + int(minutes)


def local_time(timezone_name: str, now: dt.datetime | None = None) -> dt.datetime:
    if timezone_name == "local":
        return now.astimezone() if now is not None else dt.datetime.now().astimezone()
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone_name}") from exc
    if now is None:
        return dt.datetime.now(timezone)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone)
    return now.astimezone(timezone)


@dataclass(frozen=True)
class AlertPolicy:
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"

    def __post_init__(self) -> None:
        if not isinstance(self.quiet_hours_enabled, bool):
            raise ValueError("quiet_hours_enabled must be a boolean")
        clock_minutes(self.quiet_hours_start)
        clock_minutes(self.quiet_hours_end)

    @classmethod
    def from_dict(cls, payload: object) -> "AlertPolicy":
        if not isinstance(payload, dict):
            raise ValueError("alert policy must be a JSON object")
        required = {"quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end"}
        if not required.issubset(payload):
            raise ValueError("alert policy requires enabled, start, and end values")
        return cls(
            quiet_hours_enabled=payload["quiet_hours_enabled"],
            quiet_hours_start=payload["quiet_hours_start"],
            quiet_hours_end=payload["quiet_hours_end"],
        )

    def quiet_now(self, timezone_name: str, now: dt.datetime | None = None) -> bool:
        if not self.quiet_hours_enabled:
            return False
        current = local_time(timezone_name, now)
        current_minutes = current.hour * 60 + current.minute
        start = clock_minutes(self.quiet_hours_start)
        end = clock_minutes(self.quiet_hours_end)
        if start == end:
            return True
        if start < end:
            return start <= current_minutes < end
        return current_minutes >= start or current_minutes < end

    def to_dict(self, timezone_name: str, now: dt.datetime | None = None) -> dict[str, object]:
        current = local_time(timezone_name, now)
        return {
            "quiet_hours_enabled": self.quiet_hours_enabled,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "quiet_now": self.quiet_now(timezone_name, current),
            "timezone": timezone_name,
            "evaluated_at": current.isoformat(),
        }


def load_alert_policy(path: Path) -> AlertPolicy:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AlertPolicy()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("alert policy file is not valid JSON") from exc
    return AlertPolicy.from_dict(payload)


def save_alert_policy(path: Path, policy: AlertPolicy) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(
                {
                    "quiet_hours_enabled": policy.quiet_hours_enabled,
                    "quiet_hours_start": policy.quiet_hours_start,
                    "quiet_hours_end": policy.quiet_hours_end,
                },
                handle,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o644)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
