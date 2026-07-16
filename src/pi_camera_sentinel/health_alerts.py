from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

from .config import Settings
from .health import PowerStatus, disk_status, read_cpu_temperature, read_current_power_status
from .telegram import send_message


ALERT_TYPES = {"warning", "recovered"}


@dataclass(frozen=True)
class HealthIssue:
    key: str
    label: str
    detail: str

    def __post_init__(self) -> None:
        if not self.key or not self.label or not self.detail:
            raise ValueError("health issue fields cannot be empty")

    @classmethod
    def from_dict(cls, payload: object) -> "HealthIssue":
        if not isinstance(payload, dict):
            raise ValueError("health issue must be a JSON object")
        key = payload.get("key")
        label = payload.get("label")
        detail = payload.get("detail")
        if not all(isinstance(value, str) for value in (key, label, detail)):
            raise ValueError("health issue fields must be text")
        return cls(key, label, detail)


@dataclass(frozen=True)
class HealthIssueTracker:
    issue: HealthIssue
    active: bool = False
    notified: bool = False
    present_count: int = 0
    absent_count: int = 0

    def __post_init__(self) -> None:
        if self.present_count < 0 or self.absent_count < 0:
            raise ValueError("health issue counters cannot be negative")

    @classmethod
    def from_dict(cls, payload: object) -> "HealthIssueTracker":
        if not isinstance(payload, dict):
            raise ValueError("health issue tracker must be a JSON object")
        active = payload.get("active", False)
        notified = payload.get("notified", False)
        present_count = payload.get("present_count", 0)
        absent_count = payload.get("absent_count", 0)
        if not isinstance(active, bool) or not isinstance(notified, bool):
            raise ValueError("health issue tracker flags must be booleans")
        if isinstance(present_count, bool) or not isinstance(present_count, int):
            raise ValueError("health issue present count must be an integer")
        if isinstance(absent_count, bool) or not isinstance(absent_count, int):
            raise ValueError("health issue absent count must be an integer")
        return cls(
            issue=HealthIssue.from_dict(payload.get("issue")),
            active=active,
            notified=notified,
            present_count=present_count,
            absent_count=absent_count,
        )


@dataclass(frozen=True)
class HealthAlert:
    type: str
    occurred_at: str
    issues: tuple[HealthIssue, ...]

    def __post_init__(self) -> None:
        if self.type not in ALERT_TYPES:
            raise ValueError("unknown health alert type")
        if not self.occurred_at or not self.issues:
            raise ValueError("health alert requires a timestamp and issues")

    @classmethod
    def from_dict(cls, payload: object) -> "HealthAlert":
        if not isinstance(payload, dict):
            raise ValueError("health alert must be a JSON object")
        alert_type = payload.get("type")
        occurred_at = payload.get("occurred_at")
        raw_issues = payload.get("issues")
        if not isinstance(alert_type, str) or not isinstance(occurred_at, str):
            raise ValueError("health alert text fields are invalid")
        if not isinstance(raw_issues, list):
            raise ValueError("health alert issues must be a list")
        return cls(
            type=alert_type,
            occurred_at=occurred_at,
            issues=tuple(HealthIssue.from_dict(issue) for issue in raw_issues),
        )


@dataclass(frozen=True)
class HealthAlertState:
    initialized: bool = False
    last_checked_at: str | None = None
    trackers: tuple[HealthIssueTracker, ...] = ()
    pending_alerts: tuple[HealthAlert, ...] = ()

    def __post_init__(self) -> None:
        keys = [tracker.issue.key for tracker in self.trackers]
        if len(keys) != len(set(keys)):
            raise ValueError("health alert state contains duplicate issue trackers")

    @classmethod
    def from_dict(cls, payload: object) -> "HealthAlertState":
        if not isinstance(payload, dict):
            raise ValueError("health alert state must be a JSON object")
        initialized = payload.get("initialized", False)
        last_checked_at = payload.get("last_checked_at")
        raw_trackers = payload.get("trackers", [])
        raw_alerts = payload.get("pending_alerts", [])
        if not isinstance(initialized, bool):
            raise ValueError("health alert initialized flag must be a boolean")
        if last_checked_at is not None and not isinstance(last_checked_at, str):
            raise ValueError("health alert last check must be text or null")
        if not isinstance(raw_trackers, list) or not isinstance(raw_alerts, list):
            raise ValueError("health alert trackers and pending alerts must be lists")
        return cls(
            initialized=initialized,
            last_checked_at=last_checked_at,
            trackers=tuple(HealthIssueTracker.from_dict(item) for item in raw_trackers),
            pending_alerts=tuple(HealthAlert.from_dict(item) for item in raw_alerts),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_health_alert_state(path: Path) -> HealthAlertState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return HealthAlertState()
    except json.JSONDecodeError as exc:
        raise ValueError("health alert state file is not valid JSON") from exc
    return HealthAlertState.from_dict(payload)


def save_health_alert_state(path: Path, state: HealthAlertState) -> None:
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
            json.dump(state.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o644)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def validate_health_alert_config(settings: Settings) -> None:
    if settings.health_interval_seconds <= 0:
        raise ValueError("health alert interval must be greater than zero")
    if settings.health_failure_threshold < 1:
        raise ValueError("health alert failure threshold must be at least one")
    if settings.health_recovery_threshold < 1:
        raise ValueError("health alert recovery threshold must be at least one")
    if settings.health_temperature_max_c <= 0:
        raise ValueError("health alert temperature limit must be greater than zero")


def collect_health_issues(
    settings: Settings,
    *,
    power_reader: Callable[[], PowerStatus] = read_current_power_status,
    temperature_reader: Callable[[], float | None] = read_cpu_temperature,
    disk_reader: Callable[[Path, int], tuple[Path, int, int, bool]] = disk_status,
) -> tuple[HealthIssue, ...]:
    issues: list[HealthIssue] = []
    power = power_reader()
    if power.state == "active":
        detail = ", ".join(power.current_issues) or "Pi hardware power limit active"
        issues.append(HealthIssue("power", "Power", detail))

    temperature = temperature_reader()
    if temperature is not None and temperature >= settings.health_temperature_max_c:
        issues.append(
            HealthIssue(
                "temperature",
                "Temperature",
                f"{temperature:.1f} C (limit {settings.health_temperature_max_c:g} C)",
            )
        )

    disk_path, free_bytes, _total_bytes, disk_low = disk_reader(
        settings.output_dir,
        settings.disk_min_free_mb,
    )
    if disk_low:
        free_mb = free_bytes / (1024 * 1024)
        issues.append(
            HealthIssue(
                "storage",
                "Storage",
                f"{free_mb:.0f} MB free at {disk_path} (minimum {settings.disk_min_free_mb} MB)",
            )
        )
    return tuple(issues)


def health_watchdog_step(
    settings: Settings,
    state: HealthAlertState,
    issues: tuple[HealthIssue, ...],
    *,
    now: dt.datetime | None = None,
) -> HealthAlertState:
    validate_health_alert_config(settings)
    checked_at = (now or dt.datetime.now(dt.timezone.utc)).isoformat()
    current = {issue.key: issue for issue in issues}

    if not state.initialized:
        baseline = tuple(
            HealthIssueTracker(issue=issue, active=True, notified=False)
            for issue in sorted(current.values(), key=lambda item: item.key)
        )
        return replace(
            state,
            initialized=True,
            last_checked_at=checked_at,
            trackers=baseline,
        )

    previous = {tracker.issue.key: tracker for tracker in state.trackers}
    trackers: list[HealthIssueTracker] = []
    activated: list[HealthIssue] = []
    recovered: list[HealthIssue] = []

    for key in sorted(set(previous) | set(current)):
        tracker = previous.get(key)
        issue = current.get(key)
        if issue is not None:
            if tracker is not None and tracker.active:
                trackers.append(
                    replace(
                        tracker,
                        issue=issue,
                        present_count=0,
                        absent_count=0,
                    )
                )
                continue
            present_count = (tracker.present_count if tracker is not None else 0) + 1
            if present_count >= settings.health_failure_threshold:
                trackers.append(
                    HealthIssueTracker(issue=issue, active=True, notified=True)
                )
                activated.append(issue)
            else:
                trackers.append(
                    HealthIssueTracker(issue=issue, present_count=present_count)
                )
            continue

        if tracker is None or not tracker.active:
            continue
        absent_count = tracker.absent_count + 1
        if absent_count >= settings.health_recovery_threshold:
            if tracker.notified:
                recovered.append(tracker.issue)
            continue
        trackers.append(
            replace(tracker, present_count=0, absent_count=absent_count)
        )

    pending = list(state.pending_alerts)
    if activated:
        pending.append(HealthAlert("warning", checked_at, tuple(activated)))
    if recovered:
        pending.append(HealthAlert("recovered", checked_at, tuple(recovered)))
    return replace(
        state,
        initialized=True,
        last_checked_at=checked_at,
        trackers=tuple(trackers),
        pending_alerts=tuple(pending),
    )


def health_alert_text(settings: Settings, alert: HealthAlert) -> str:
    heading = "system health warning" if alert.type == "warning" else "system health recovered"
    lines = [f"{settings.dashboard_title}: {heading}"]
    for issue in alert.issues:
        if alert.type == "warning":
            lines.append(f"{issue.label}: {issue.detail}")
        else:
            lines.append(f"{issue.label}: cleared")
    if settings.feed_url:
        lines.append(f"Live feed: {settings.feed_url}")
    return "\n".join(lines)


def process_health_alerts(
    settings: Settings,
    state: HealthAlertState,
    *,
    sender: Callable[[Settings, str], None] = send_message,
    saver: Callable[[Path, HealthAlertState], None] = save_health_alert_state,
) -> HealthAlertState:
    if not state.pending_alerts:
        return state
    configured = settings.health_telegram_alerts and not settings.missing_telegram_fields()
    if not configured:
        updated = replace(state, pending_alerts=())
        saver(settings.health_state_file, updated)
        return updated

    updated = state
    while updated.pending_alerts:
        sender(settings, health_alert_text(settings, updated.pending_alerts[0]))
        updated = replace(updated, pending_alerts=updated.pending_alerts[1:])
        saver(settings.health_state_file, updated)
    return updated
