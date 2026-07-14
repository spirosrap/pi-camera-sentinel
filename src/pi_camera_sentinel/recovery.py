from __future__ import annotations

import datetime as dt
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

import requests

from .config import Settings
from .services import restart_service, valid_service_name


RECOVERY_STATUSES = {
    "unknown",
    "healthy",
    "failing",
    "cooldown",
    "restarted",
    "failed",
    "unavailable",
}
RECOVERY_EVENT_TYPES = {
    "feed_unhealthy",
    "stream_restarted",
    "feed_recovered",
    "restart_failed",
}
RECOVERY_EVENT_TRIGGERS = {"automatic", "manual"}
MAX_RECOVERY_EVENTS = 20


@dataclass(frozen=True)
class FeedProbe:
    ok: bool
    checked_at: str
    reason: str
    status_code: int | None = None
    frame_age_seconds: float | None = None


@dataclass(frozen=True)
class RecoveryEvent:
    type: str
    occurred_at: str
    reason: str
    trigger: str | None = None

    def __post_init__(self) -> None:
        if self.type not in RECOVERY_EVENT_TYPES:
            raise ValueError("unknown recovery event type")
        if not self.occurred_at or not self.reason:
            raise ValueError("recovery event timestamp and reason are required")
        if self.trigger is not None and self.trigger not in RECOVERY_EVENT_TRIGGERS:
            raise ValueError("unknown recovery event trigger")

    @classmethod
    def from_dict(cls, payload: object) -> "RecoveryEvent":
        if not isinstance(payload, dict):
            raise ValueError("recovery event must be a JSON object")
        event_type = payload.get("type")
        occurred_at = payload.get("occurred_at")
        reason = payload.get("reason")
        trigger = payload.get("trigger")
        if not isinstance(event_type, str) or not isinstance(occurred_at, str) or not isinstance(reason, str):
            raise ValueError("recovery event text fields are invalid")
        if trigger is not None and not isinstance(trigger, str):
            raise ValueError("recovery event trigger must be text or null")
        return cls(event_type, occurred_at, reason, trigger)


@dataclass(frozen=True)
class RecoveryState:
    status: str = "unknown"
    stream_service: str = ""
    consecutive_failures: int = 0
    restart_count: int = 0
    last_checked_at: str | None = None
    last_healthy_at: str | None = None
    last_failure_at: str | None = None
    last_restart_at: str | None = None
    cooldown_until: str | None = None
    last_reason: str = "No checks recorded"
    events: tuple[RecoveryEvent, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in RECOVERY_STATUSES:
            raise ValueError("unknown recovery status")
        if self.consecutive_failures < 0 or self.restart_count < 0:
            raise ValueError("recovery counters cannot be negative")
        if len(self.events) > MAX_RECOVERY_EVENTS:
            raise ValueError("too many recovery events")
        if not all(isinstance(event, RecoveryEvent) for event in self.events):
            raise ValueError("recovery events are invalid")

    @classmethod
    def from_dict(cls, payload: object, *, stream_service: str = "") -> "RecoveryState":
        if not isinstance(payload, dict):
            raise ValueError("recovery state must be a JSON object")

        def optional_text(name: str) -> str | None:
            value = payload.get(name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"recovery state {name} must be text or null")
            return value

        def counter(name: str) -> int:
            value = payload.get(name, 0)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"recovery state {name} must be an integer")
            return value

        status = payload.get("status", "unknown")
        reason = payload.get("last_reason", "No checks recorded")
        stored_service = payload.get("stream_service", stream_service)
        if not isinstance(status, str) or not isinstance(reason, str) or not isinstance(stored_service, str):
            raise ValueError("recovery state text fields are invalid")
        raw_events = payload.get("events", [])
        if not isinstance(raw_events, list):
            raise ValueError("recovery state events must be a list")
        events = tuple(RecoveryEvent.from_dict(event) for event in raw_events)
        return cls(
            status=status,
            stream_service=stored_service or stream_service,
            consecutive_failures=counter("consecutive_failures"),
            restart_count=counter("restart_count"),
            last_checked_at=optional_text("last_checked_at"),
            last_healthy_at=optional_text("last_healthy_at"),
            last_failure_at=optional_text("last_failure_at"),
            last_restart_at=optional_text("last_restart_at"),
            cooldown_until=optional_text("cooldown_until"),
            last_reason=reason,
            events=events[-MAX_RECOVERY_EVENTS:],
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_recovery_state(path: Path, *, stream_service: str = "") -> RecoveryState:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return RecoveryState(stream_service=stream_service)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("recovery state file is not valid JSON") from exc
    return RecoveryState.from_dict(payload, stream_service=stream_service)


def save_recovery_state(path: Path, state: RecoveryState) -> None:
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


def validate_recovery_config(settings: Settings) -> None:
    if not valid_service_name(settings.stream_service):
        raise ValueError("recovery stream service name is invalid")
    if settings.recovery_interval_seconds < 1 or settings.recovery_interval_seconds > 3600:
        raise ValueError("recovery interval must be between 1 and 3600 seconds")
    if settings.recovery_failure_threshold < 1 or settings.recovery_failure_threshold > 20:
        raise ValueError("recovery failure threshold must be between 1 and 20")
    if settings.recovery_stale_seconds < 1 or settings.recovery_stale_seconds > 3600:
        raise ValueError("recovery stale-frame limit must be between 1 and 3600 seconds")
    if settings.recovery_cooldown_seconds < 10 or settings.recovery_cooldown_seconds > 86400:
        raise ValueError("recovery cooldown must be between 10 and 86400 seconds")


def probe_feed(
    settings: Settings,
    *,
    get: Callable[..., requests.Response] = requests.get,
    now: dt.datetime | None = None,
) -> FeedProbe:
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    checked_at = current.isoformat()
    try:
        response = get(settings.snapshot_url, timeout=settings.http_timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        return FeedProbe(False, checked_at, f"snapshot request failed ({type(exc).__name__})")

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        return FeedProbe(False, checked_at, "snapshot response is not an image", response.status_code)
    if not response.content:
        return FeedProbe(False, checked_at, "snapshot response is empty", response.status_code)
    if response.headers.get("x-ustreamer-online", "true").strip().lower() in {"0", "false", "no", "off"}:
        return FeedProbe(False, checked_at, "camera reports offline", response.status_code)

    frame_age: float | None = None
    timestamp = response.headers.get("x-timestamp")
    if timestamp:
        try:
            frame_timestamp = float(timestamp)
        except ValueError:
            return FeedProbe(False, checked_at, "frame timestamp is invalid", response.status_code)
        if not math.isfinite(frame_timestamp):
            return FeedProbe(False, checked_at, "frame timestamp is invalid", response.status_code)
        frame_age = round(max(0.0, current.timestamp() - frame_timestamp), 3)
        if frame_age > settings.recovery_stale_seconds:
            return FeedProbe(
                False,
                checked_at,
                f"frame is {frame_age:g}s old",
                response.status_code,
                frame_age,
            )

    return FeedProbe(True, checked_at, "snapshot healthy", response.status_code, frame_age)


def _parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def append_recovery_event(
    state: RecoveryState,
    event_type: str,
    occurred_at: str,
    reason: str,
    *,
    trigger: str | None = None,
) -> RecoveryState:
    event = RecoveryEvent(event_type, occurred_at, reason, trigger)
    return replace(state, events=(*state.events, event)[-MAX_RECOVERY_EVENTS:])


def manual_restart_feed(
    settings: Settings,
    state: RecoveryState,
    *,
    restarter: Callable[[str], None] = restart_service,
    now: dt.datetime | None = None,
) -> RecoveryState:
    validate_recovery_config(settings)
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    occurred_at = current.isoformat()
    cooldown_until = current + dt.timedelta(seconds=settings.recovery_cooldown_seconds)
    try:
        restarter(settings.stream_service)
    except (OSError, ValueError) as exc:
        updated = replace(
            state,
            status="failed",
            stream_service=settings.stream_service,
            cooldown_until=cooldown_until.isoformat(),
            last_reason="Manual stream restart failed",
        )
        updated = append_recovery_event(
            updated,
            "restart_failed",
            occurred_at,
            updated.last_reason,
            trigger="manual",
        )
        save_recovery_state(settings.recovery_state_file, updated)
        raise OSError("manual stream restart failed") from exc

    updated = replace(
        state,
        status="restarted",
        stream_service=settings.stream_service,
        consecutive_failures=0,
        restart_count=state.restart_count + 1,
        last_restart_at=occurred_at,
        cooldown_until=cooldown_until.isoformat(),
        last_reason="Manual feed restart requested",
    )
    updated = append_recovery_event(
        updated,
        "stream_restarted",
        occurred_at,
        updated.last_reason,
        trigger="manual",
    )
    save_recovery_state(settings.recovery_state_file, updated)
    return updated


def recovery_watchdog_step(
    settings: Settings,
    state: RecoveryState,
    *,
    probe: Callable[[Settings], FeedProbe] | None = None,
    restarter: Callable[[str], None] = restart_service,
    now: dt.datetime | None = None,
) -> RecoveryState:
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    result = probe(settings) if probe is not None else probe_feed(settings, now=current)
    common = {
        "stream_service": settings.stream_service,
        "last_checked_at": result.checked_at,
        "last_reason": result.reason,
    }

    if result.ok:
        updated = replace(
            state,
            **common,
            status="healthy",
            consecutive_failures=0,
            last_healthy_at=result.checked_at,
        )
        if state.status in {"failing", "cooldown", "restarted", "failed"}:
            updated = append_recovery_event(
                updated,
                "feed_recovered",
                result.checked_at,
                result.reason,
            )
        save_recovery_state(settings.recovery_state_file, updated)
        return updated

    failures = min(state.consecutive_failures + 1, settings.recovery_failure_threshold)
    updated = replace(
        state,
        **common,
        status="failing",
        consecutive_failures=failures,
        last_failure_at=result.checked_at,
    )
    if state.status not in {"failing", "cooldown", "failed"}:
        updated = append_recovery_event(
            updated,
            "feed_unhealthy",
            result.checked_at,
            result.reason,
        )
    if failures < settings.recovery_failure_threshold:
        save_recovery_state(settings.recovery_state_file, updated)
        return updated

    cooldown_until = _parse_time(state.cooldown_until)
    if cooldown_until is not None and current < cooldown_until:
        updated = replace(updated, status="cooldown")
        save_recovery_state(settings.recovery_state_file, updated)
        return updated

    next_cooldown = current + dt.timedelta(seconds=settings.recovery_cooldown_seconds)
    try:
        restarter(settings.stream_service)
    except (OSError, ValueError):
        updated = replace(
            updated,
            status="failed",
            cooldown_until=next_cooldown.isoformat(),
            last_reason=f"{result.reason}; stream restart failed",
        )
        updated = append_recovery_event(
            updated,
            "restart_failed",
            current.isoformat(),
            updated.last_reason,
            trigger="automatic",
        )
    else:
        updated = replace(
            updated,
            status="restarted",
            consecutive_failures=0,
            restart_count=state.restart_count + 1,
            last_restart_at=current.isoformat(),
            cooldown_until=next_cooldown.isoformat(),
        )
        updated = append_recovery_event(
            updated,
            "stream_restarted",
            current.isoformat(),
            result.reason,
            trigger="automatic",
        )
    save_recovery_state(settings.recovery_state_file, updated)
    return updated
