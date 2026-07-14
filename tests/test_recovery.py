import datetime as dt
from dataclasses import replace

import pytest
import requests

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.recovery import (
    FeedProbe,
    RecoveryState,
    load_recovery_state,
    probe_feed,
    recovery_watchdog_step,
    save_recovery_state,
    validate_recovery_config,
)


class FakeResponse:
    def __init__(self, *, headers=None, content=b"jpeg", status_code=200):
        self.headers = headers or {"content-type": "image/jpeg"}
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def recovery_settings(tmp_path, **changes) -> Settings:
    values = {
        "recovery_state_file": tmp_path / "recovery-state.json",
        "recovery_failure_threshold": 2,
        "recovery_cooldown_seconds": 120,
        "recovery_stale_seconds": 20,
        "stream_service": "camera-stream.service",
    }
    values.update(changes)
    return replace(Settings.from_env(), **values)


def test_probe_feed_accepts_fresh_image_and_rejects_stale_frame(tmp_path):
    now = dt.datetime(2026, 7, 14, 20, 0, tzinfo=dt.timezone.utc)
    settings = recovery_settings(tmp_path)
    fresh = FakeResponse(
        headers={
            "content-type": "image/jpeg",
            "x-ustreamer-online": "true",
            "x-timestamp": str(now.timestamp() - 2),
        }
    )
    stale = FakeResponse(
        headers={
            "content-type": "image/jpeg",
            "x-timestamp": str(now.timestamp() - 21),
        }
    )

    healthy = probe_feed(settings, get=lambda *_args, **_kwargs: fresh, now=now)
    unhealthy = probe_feed(settings, get=lambda *_args, **_kwargs: stale, now=now)

    assert healthy.ok is True
    assert healthy.frame_age_seconds == 2.0
    assert unhealthy.ok is False
    assert unhealthy.reason == "frame is 21s old"


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (FakeResponse(headers={"content-type": "text/plain"}), "snapshot response is not an image"),
        (FakeResponse(content=b""), "snapshot response is empty"),
        (
            FakeResponse(headers={"content-type": "image/jpeg", "x-ustreamer-online": "false"}),
            "camera reports offline",
        ),
    ],
)
def test_probe_feed_rejects_invalid_snapshot_responses(tmp_path, response, reason):
    result = probe_feed(
        recovery_settings(tmp_path),
        get=lambda *_args, **_kwargs: response,
    )

    assert result.ok is False
    assert result.reason == reason


def test_recovery_restarts_after_threshold_and_obeys_cooldown(tmp_path):
    settings = recovery_settings(tmp_path)
    state = RecoveryState(stream_service=settings.stream_service)
    restarts = []
    start = dt.datetime(2026, 7, 14, 20, 0, tzinfo=dt.timezone.utc)

    def failed_probe(_settings):
        return FeedProbe(False, start.isoformat(), "camera reports offline")

    state = recovery_watchdog_step(
        settings,
        state,
        probe=failed_probe,
        restarter=restarts.append,
        now=start,
    )
    assert state.status == "failing"
    assert restarts == []

    state = recovery_watchdog_step(
        settings,
        state,
        probe=failed_probe,
        restarter=restarts.append,
        now=start + dt.timedelta(seconds=15),
    )
    assert state.status == "restarted"
    assert state.restart_count == 1
    assert restarts == ["camera-stream.service"]

    state = recovery_watchdog_step(
        settings,
        state,
        probe=failed_probe,
        restarter=restarts.append,
        now=start + dt.timedelta(seconds=30),
    )
    state = recovery_watchdog_step(
        settings,
        state,
        probe=failed_probe,
        restarter=restarts.append,
        now=start + dt.timedelta(seconds=45),
    )
    assert state.status == "cooldown"
    assert restarts == ["camera-stream.service"]


def test_recovery_state_round_trip_and_healthy_reset(tmp_path):
    settings = recovery_settings(tmp_path)
    previous = RecoveryState(
        status="failing",
        stream_service=settings.stream_service,
        consecutive_failures=1,
        restart_count=2,
        last_reason="offline",
    )
    save_recovery_state(settings.recovery_state_file, previous)

    loaded = load_recovery_state(
        settings.recovery_state_file,
        stream_service=settings.stream_service,
    )
    result = recovery_watchdog_step(
        settings,
        loaded,
        probe=lambda _settings: FeedProbe(
            True,
            "2026-07-14T20:00:00+00:00",
            "snapshot healthy",
            200,
            0.5,
        ),
    )

    assert result.status == "healthy"
    assert result.consecutive_failures == 0
    assert result.restart_count == 2
    assert load_recovery_state(settings.recovery_state_file) == result


def test_recovery_configuration_rejects_unsafe_service_name(tmp_path):
    settings = recovery_settings(tmp_path, stream_service="camera.service;reboot")

    with pytest.raises(ValueError, match="service name"):
        validate_recovery_config(settings)
