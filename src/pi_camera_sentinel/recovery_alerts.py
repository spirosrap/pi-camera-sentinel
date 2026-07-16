from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from .config import Settings
from .recovery import RecoveryEvent, RecoveryState, save_recovery_state
from .telegram import send_message


EMPTY_RECOVERY_CURSOR = "start"


def recovery_event_key(event: RecoveryEvent) -> str:
    return "|".join((event.occurred_at, event.type, event.trigger or ""))


def initialize_recovery_alert_cursor(state: RecoveryState) -> RecoveryState:
    if state.recovery_notification_cursor is not None:
        return state
    cursor = recovery_event_key(state.events[-1]) if state.events else EMPTY_RECOVERY_CURSOR
    return replace(state, recovery_notification_cursor=cursor)


def pending_recovery_event_indexes(state: RecoveryState) -> tuple[int, ...]:
    cursor = state.recovery_notification_cursor
    if cursor is None:
        return ()
    if cursor == EMPTY_RECOVERY_CURSOR:
        return tuple(range(len(state.events)))
    for index, event in enumerate(state.events):
        if recovery_event_key(event) == cursor:
            return tuple(range(index + 1, len(state.events)))
    return tuple(range(len(state.events)))


def follows_automatic_incident(events: tuple[RecoveryEvent, ...], index: int) -> bool:
    for previous in reversed(events[:index]):
        if previous.type == "feed_recovered":
            return False
        if previous.type in {"stream_restarted", "restart_failed"}:
            return previous.trigger == "automatic"
    return False


def should_send_recovery_alert(events: tuple[RecoveryEvent, ...], index: int) -> bool:
    event = events[index]
    if event.type in {"stream_restarted", "restart_failed"}:
        return event.trigger == "automatic"
    if event.type == "feed_recovered":
        return follows_automatic_incident(events, index)
    return False


def recovery_alert_text(settings: Settings, event: RecoveryEvent) -> str:
    labels = {
        "stream_restarted": "camera feed restarted automatically",
        "restart_failed": "automatic camera feed restart failed",
        "feed_recovered": "camera feed recovered",
    }
    lines = [f"{settings.dashboard_title}: {labels[event.type]}", f"Reason: {event.reason}"]
    if settings.feed_url:
        lines.append(f"Live feed: {settings.feed_url}")
    return "\n".join(lines)


def process_recovery_alerts(
    settings: Settings,
    state: RecoveryState,
    *,
    sender: Callable[[Settings, str], None] = send_message,
    saver: Callable[[Path, RecoveryState], None] = save_recovery_state,
) -> RecoveryState:
    configured = settings.recovery_telegram_alerts and not settings.missing_telegram_fields()
    updated = state
    for index in pending_recovery_event_indexes(state):
        event = state.events[index]
        if configured and should_send_recovery_alert(state.events, index):
            sender(settings, recovery_alert_text(settings, event))
        updated = replace(
            updated,
            recovery_notification_cursor=recovery_event_key(event),
        )
        saver(settings.recovery_state_file, updated)
    return updated
