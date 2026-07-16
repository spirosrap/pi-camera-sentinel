from __future__ import annotations

from dataclasses import replace

import pytest

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.recovery import RecoveryEvent, RecoveryState
from pi_camera_sentinel.recovery_alerts import (
    EMPTY_RECOVERY_CURSOR,
    initialize_recovery_alert_cursor,
    process_recovery_alerts,
    recovery_event_key,
)


def alert_settings(tmp_path, **changes) -> Settings:
    values = {
        "dashboard_title": "Garden camera",
        "feed_url": "https://camera.example/stream",
        "recovery_state_file": tmp_path / "recovery-state.json",
        "recovery_telegram_alerts": True,
        "telegram_token": "token",
        "telegram_chat_id": "123",
    }
    values.update(changes)
    return replace(Settings.from_env(), **values)


def event(
    event_type: str,
    second: int,
    *,
    trigger: str | None = None,
    reason: str = "camera reports offline",
) -> RecoveryEvent:
    return RecoveryEvent(
        event_type,
        f"2026-07-16T08:00:{second:02d}+00:00",
        reason,
        trigger,
    )


def test_alert_cursor_migration_skips_existing_history():
    existing = event("stream_restarted", 10, trigger="automatic")
    state = RecoveryState(events=(existing,))

    prepared = initialize_recovery_alert_cursor(state)

    assert prepared.recovery_notification_cursor == recovery_event_key(existing)
    assert initialize_recovery_alert_cursor(RecoveryState()).recovery_notification_cursor == (
        EMPTY_RECOVERY_CURSOR
    )


def test_automatic_restart_and_recovery_send_once(tmp_path):
    unhealthy = event("feed_unhealthy", 0)
    restarted = event("stream_restarted", 15, trigger="automatic")
    recovered = event("feed_recovered", 30, reason="snapshot healthy")
    settings = alert_settings(tmp_path)
    sent = []
    saved = []
    state = RecoveryState(
        events=(unhealthy, restarted),
        recovery_notification_cursor=recovery_event_key(unhealthy),
    )

    state = process_recovery_alerts(
        settings,
        state,
        sender=lambda _settings, text: sent.append(text),
        saver=lambda _path, current: saved.append(current),
    )

    assert sent == [
        "Garden camera: camera feed restarted automatically\n"
        "Reason: camera reports offline\n"
        "Live feed: https://camera.example/stream"
    ]
    assert state.recovery_notification_cursor == recovery_event_key(restarted)

    state = replace(state, events=(*state.events, recovered))
    state = process_recovery_alerts(
        settings,
        state,
        sender=lambda _settings, text: sent.append(text),
        saver=lambda _path, current: saved.append(current),
    )

    assert sent[-1] == (
        "Garden camera: camera feed recovered\n"
        "Reason: snapshot healthy\n"
        "Live feed: https://camera.example/stream"
    )
    assert state.recovery_notification_cursor == recovery_event_key(recovered)
    assert len(saved) == 2


def test_failed_send_keeps_event_pending_for_retry(tmp_path):
    baseline = event("feed_unhealthy", 0)
    restarted = event("stream_restarted", 15, trigger="automatic")
    state = RecoveryState(
        events=(baseline, restarted),
        recovery_notification_cursor=recovery_event_key(baseline),
    )
    saved = []

    with pytest.raises(RuntimeError, match="Telegram offline"):
        process_recovery_alerts(
            alert_settings(tmp_path),
            state,
            sender=lambda *_args: (_ for _ in ()).throw(RuntimeError("Telegram offline")),
            saver=lambda _path, current: saved.append(current),
        )

    assert state.recovery_notification_cursor == recovery_event_key(baseline)
    assert saved == []

    sent = []
    result = process_recovery_alerts(
        alert_settings(tmp_path),
        state,
        sender=lambda _settings, text: sent.append(text),
        saver=lambda _path, current: saved.append(current),
    )
    assert len(sent) == 1
    assert result.recovery_notification_cursor == recovery_event_key(restarted)


@pytest.mark.parametrize("enabled", [False, True])
def test_disabled_or_unconfigured_alerts_advance_without_sending(tmp_path, enabled):
    restarted = event("stream_restarted", 15, trigger="automatic")
    state = RecoveryState(
        events=(restarted,),
        recovery_notification_cursor=EMPTY_RECOVERY_CURSOR,
    )
    settings = alert_settings(
        tmp_path,
        recovery_telegram_alerts=enabled,
        telegram_token="" if enabled else "token",
    )

    result = process_recovery_alerts(
        settings,
        state,
        sender=lambda *_args: pytest.fail("alert should not be sent"),
        saver=lambda *_args: None,
    )

    assert result.recovery_notification_cursor == recovery_event_key(restarted)


def test_manual_restart_and_transient_failure_do_not_send(tmp_path):
    transient = event("feed_unhealthy", 0)
    transient_recovery = event("feed_recovered", 5, reason="snapshot healthy")
    manual = event("stream_restarted", 10, trigger="manual")
    manual_recovery = event("feed_recovered", 15, reason="snapshot healthy")
    state = RecoveryState(
        events=(transient, transient_recovery, manual, manual_recovery),
        recovery_notification_cursor=EMPTY_RECOVERY_CURSOR,
    )

    result = process_recovery_alerts(
        alert_settings(tmp_path),
        state,
        sender=lambda *_args: pytest.fail("alert should not be sent"),
        saver=lambda *_args: None,
    )

    assert result.recovery_notification_cursor == recovery_event_key(manual_recovery)
