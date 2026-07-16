from __future__ import annotations

import datetime as dt
from dataclasses import replace

import pytest

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.health import power_status_from_flags
from pi_camera_sentinel.health_alerts import (
    HealthAlertState,
    HealthIssue,
    collect_health_issues,
    health_watchdog_step,
    load_health_alert_state,
    process_health_alerts,
    save_health_alert_state,
    validate_health_alert_config,
)


def alert_settings(tmp_path, **changes) -> Settings:
    values = {
        "dashboard_title": "Garden camera",
        "feed_url": "https://camera.example/stream",
        "health_state_file": tmp_path / "health-alert-state.json",
        "health_interval_seconds": 60,
        "health_failure_threshold": 2,
        "health_recovery_threshold": 2,
        "health_temperature_max_c": 80,
        "health_telegram_alerts": True,
        "telegram_token": "token",
        "telegram_chat_id": "123",
    }
    values.update(changes)
    return replace(Settings.from_env(), **values)


def checked(second: int) -> dt.datetime:
    return dt.datetime(2026, 7, 16, 8, 0, second, tzinfo=dt.timezone.utc)


def power_issue(detail: str = "Undervoltage, CPU throttled") -> HealthIssue:
    return HealthIssue("power", "Power", detail)


def test_first_sample_baselines_existing_issue_without_alert(tmp_path):
    state = health_watchdog_step(
        alert_settings(tmp_path),
        HealthAlertState(),
        (power_issue(),),
        now=checked(0),
    )

    assert state.initialized is True
    assert state.pending_alerts == ()
    assert len(state.trackers) == 1
    assert state.trackers[0].active is True
    assert state.trackers[0].notified is False


def test_confirmed_warning_and_recovery_each_send_once(tmp_path):
    settings = alert_settings(tmp_path)
    state = health_watchdog_step(settings, HealthAlertState(), (), now=checked(0))

    state = health_watchdog_step(settings, state, (power_issue(),), now=checked(1))
    assert state.trackers[0].present_count == 1
    assert state.pending_alerts == ()

    state = health_watchdog_step(settings, state, (power_issue(),), now=checked(2))
    assert state.trackers[0].active is True
    assert state.trackers[0].notified is True
    assert [alert.type for alert in state.pending_alerts] == ["warning"]

    sent = []
    state = process_health_alerts(
        settings,
        state,
        sender=lambda _settings, text: sent.append(text),
        saver=lambda *_args: None,
    )
    assert sent == [
        "Garden camera: system health warning\n"
        "Power: Undervoltage, CPU throttled\n"
        "Live feed: https://camera.example/stream"
    ]
    assert state.pending_alerts == ()

    state = health_watchdog_step(settings, state, (), now=checked(3))
    assert state.trackers[0].absent_count == 1
    state = health_watchdog_step(settings, state, (), now=checked(4))
    assert state.trackers == ()
    assert [alert.type for alert in state.pending_alerts] == ["recovered"]

    state = process_health_alerts(
        settings,
        state,
        sender=lambda _settings, text: sent.append(text),
        saver=lambda *_args: None,
    )
    assert sent[-1] == (
        "Garden camera: system health recovered\n"
        "Power: cleared\n"
        "Live feed: https://camera.example/stream"
    )
    assert state.pending_alerts == ()


def test_transient_issue_does_not_alert(tmp_path):
    settings = alert_settings(tmp_path, health_failure_threshold=3)
    state = health_watchdog_step(settings, HealthAlertState(), (), now=checked(0))
    state = health_watchdog_step(settings, state, (power_issue(),), now=checked(1))
    state = health_watchdog_step(settings, state, (), now=checked(2))

    assert state.trackers == ()
    assert state.pending_alerts == ()


def test_failed_delivery_stays_pending_and_retries(tmp_path):
    settings = alert_settings(tmp_path, health_failure_threshold=1)
    state = health_watchdog_step(settings, HealthAlertState(), (), now=checked(0))
    state = health_watchdog_step(settings, state, (power_issue(),), now=checked(1))
    saved = []

    with pytest.raises(RuntimeError, match="Telegram offline"):
        process_health_alerts(
            settings,
            state,
            sender=lambda *_args: (_ for _ in ()).throw(RuntimeError("Telegram offline")),
            saver=lambda _path, current: saved.append(current),
        )

    assert len(state.pending_alerts) == 1
    assert saved == []

    sent = []
    result = process_health_alerts(
        settings,
        state,
        sender=lambda _settings, text: sent.append(text),
        saver=lambda _path, current: saved.append(current),
    )
    assert len(sent) == 1
    assert result.pending_alerts == ()
    assert saved[-1] == result


def test_disabled_alerts_clear_pending_without_sending(tmp_path):
    settings = alert_settings(
        tmp_path,
        health_failure_threshold=1,
        health_telegram_alerts=False,
    )
    state = health_watchdog_step(settings, HealthAlertState(), (), now=checked(0))
    state = health_watchdog_step(settings, state, (power_issue(),), now=checked(1))

    result = process_health_alerts(
        settings,
        state,
        sender=lambda *_args: pytest.fail("disabled health alert should not send"),
        saver=lambda *_args: None,
    )

    assert result.pending_alerts == ()


def test_health_alert_state_round_trip(tmp_path):
    settings = alert_settings(tmp_path)
    expected = health_watchdog_step(
        settings,
        HealthAlertState(),
        (power_issue(),),
        now=checked(0),
    )

    save_health_alert_state(settings.health_state_file, expected)

    assert load_health_alert_state(settings.health_state_file) == expected


def test_collect_health_issues_reports_power_temperature_and_storage(tmp_path):
    settings = alert_settings(tmp_path, output_dir=tmp_path, disk_min_free_mb=512)
    issues = collect_health_issues(
        settings,
        power_reader=lambda: power_status_from_flags((0x5, "0x5"), False),
        temperature_reader=lambda: 82.5,
        disk_reader=lambda _path, _minimum: (tmp_path, 128 * 1024 * 1024, 1024, True),
    )

    assert [issue.key for issue in issues] == ["power", "temperature", "storage"]
    assert issues[0].detail == "Undervoltage, CPU throttled"
    assert issues[1].detail == "82.5 C (limit 80 C)"
    assert "128 MB free" in issues[2].detail


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"health_interval_seconds": 0}, "interval"),
        ({"health_failure_threshold": 0}, "failure threshold"),
        ({"health_recovery_threshold": 0}, "recovery threshold"),
        ({"health_temperature_max_c": 0}, "temperature limit"),
    ],
)
def test_validate_health_alert_config(tmp_path, changes, message):
    with pytest.raises(ValueError, match=message):
        validate_health_alert_config(alert_settings(tmp_path, **changes))
