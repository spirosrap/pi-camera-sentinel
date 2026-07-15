import io
import os
from dataclasses import replace

import pytest
import requests
from PIL import Image

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.dashboard import (
    DashboardApplication,
    collect_dashboard_status,
    event_history,
    list_recent_events,
    parse_event_query,
    same_origin,
    with_query,
)
from pi_camera_sentinel.recovery import RecoveryEvent, RecoveryState
from pi_camera_sentinel.retention import RetentionPolicy
from pi_camera_sentinel.health import power_status_from_flags


class FakeResponse:
    def __init__(self, content: bytes, headers: dict[str, str], status_code: int = 200):
        self.content = content
        self.headers = headers
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def jpeg_bytes(color: tuple[int, int, int] = (120, 120, 120)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (1280, 720), color).save(output, format="JPEG")
    return output.getvalue()


def dashboard_settings(tmp_path) -> Settings:
    return replace(
        Settings.from_env(),
        camera_device="auto",
        output_dir=tmp_path,
        disk_min_free_mb=0,
        dashboard_title="Garden camera",
        recovery_state_file=tmp_path / "recovery-state.json",
    )


def power_status(flags: int = 0, recent: bool = False):
    return power_status_from_flags((flags, hex(flags)), recent)


def test_collect_dashboard_status_for_online_feed(tmp_path):
    response = FakeResponse(
        jpeg_bytes(),
        {
            "content-type": "image/jpeg",
            "x-timestamp": "2000000000.0",
            "x-ustreamer-dropped": "0",
            "x-ustreamer-online": "true",
        },
    )

    result = collect_dashboard_status(
        dashboard_settings(tmp_path),
        power_status=power_status(),
        snapshot_get=lambda *_args, **_kwargs: response,
    )

    assert result["state"] == "online"
    assert result["ok"] is True
    assert result["title"] == "Garden camera"
    assert result["feed"]["width"] == 1280
    assert result["feed"]["height"] == 720
    assert result["feed"]["mean_luma"] == 120.0
    assert result["feed"]["dropped_frames"] == 0
    assert result["automation"]["alert_batching"] == {
        "enabled": True,
        "window_seconds": 8.0,
        "max_photos": 4,
    }
    assert result["automation"]["feed_recovery"]["state"]["status"] == "unknown"
    assert result["automation"]["feed_recovery"]["failure_threshold"] == 3
    assert result["integrations"]["home_assistant"]["configured"] is False


def test_collect_dashboard_status_marks_active_power_limit_as_degraded(tmp_path):
    response = FakeResponse(jpeg_bytes(), {"content-type": "image/jpeg"})

    result = collect_dashboard_status(
        dashboard_settings(tmp_path),
        power_status=power_status(0x50005),
        snapshot_get=lambda *_args, **_kwargs: response,
    )

    assert result["state"] == "degraded"
    assert result["system"]["undervoltage_seen"] is True
    assert result["system"]["power"]["state"] == "active"
    assert result["system"]["power"]["current_issues"] == ("Undervoltage", "CPU throttled")
    assert any("active Pi power limit" in warning for warning in result["warnings"])


def test_collect_dashboard_status_does_not_degrade_for_historical_power_flag(tmp_path):
    response = FakeResponse(jpeg_bytes(), {"content-type": "image/jpeg"})

    result = collect_dashboard_status(
        dashboard_settings(tmp_path),
        power_status=power_status(0x50000),
        snapshot_get=lambda *_args, **_kwargs: response,
    )

    assert result["state"] == "online"
    assert result["system"]["undervoltage_seen"] is False
    assert result["system"]["power"]["state"] == "historical"
    assert result["warnings"] == []


def test_collect_dashboard_status_marks_failed_snapshot_offline(tmp_path):
    def failed_snapshot(*_args, **_kwargs):
        raise requests.ConnectionError("camera stopped")

    result = collect_dashboard_status(
        dashboard_settings(tmp_path),
        power_status=power_status(),
        snapshot_get=failed_snapshot,
    )

    assert result["state"] == "offline"
    assert result["ok"] is False
    assert result["feed"]["error"] == "camera stopped"


def test_list_recent_events_sorts_and_filters(tmp_path):
    older = tmp_path / "motion-older.jpg"
    newer = tmp_path / "motion-newer.jpg"
    ignored = tmp_path / "notes.txt"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    ignored.write_text("ignored", encoding="utf-8")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    events = list_recent_events(tmp_path)

    assert [event["name"] for event in events] == ["motion-newer.jpg", "motion-older.jpg"]
    assert events[0]["url"] == "/events/motion-newer.jpg"


def test_event_history_filters_summarizes_and_paginates(tmp_path):
    now = 2_000_000.0
    timestamps = [now - 60, now - 3600, now - (3 * 86400), now - (10 * 86400)]
    for index, timestamp in enumerate(timestamps):
        path = tmp_path / f"motion-{index}.jpg"
        path.write_bytes(b"x" * (index + 1))
        os.utime(path, (timestamp, timestamp))

    first_page = event_history(tmp_path, window="24h", limit=1, now=now)

    assert [event["name"] for event in first_page["events"]] == ["motion-0.jpg"]
    assert first_page["summary"] == {
        "window_count": 2,
        "window_size_bytes": 3,
        "retained_count": 4,
        "retained_size_bytes": 10,
        "last_captured_at": "1970-01-24T03:32:20+00:00",
    }
    assert first_page["next_before"] == timestamps[0]

    second_page = event_history(
        tmp_path,
        window="24h",
        limit=1,
        before=first_page["next_before"],
        now=now,
    )
    assert [event["name"] for event in second_page["events"]] == ["motion-1.jpg"]
    assert second_page["next_before"] is None
    assert event_history(tmp_path, window="7d", now=now)["summary"]["window_count"] == 3
    assert event_history(tmp_path, window="all", now=now)["summary"]["window_count"] == 4


def test_event_history_reports_archive_retention_state(tmp_path):
    now = 2_000_000.0
    for index in range(3):
        path = tmp_path / f"motion-{index}.jpg"
        path.write_bytes(b"x" * (index + 1))
        os.utime(path, (now - index, now - index))

    result = event_history(
        tmp_path,
        window="all",
        now=now,
        retention_policy=RetentionPolicy(max_files=2),
    )

    retention = result["summary"]["retention"]
    assert retention["policy"]["max_files"] == 2
    assert retention["archive"] == {
        "file_count": 3,
        "size_bytes": 6,
        "oldest_at": "1970-01-24T03:33:18+00:00",
    }
    assert retention["cleanup"]["file_count"] == 1
    assert retention["projected_archive"]["file_count"] == 2


def test_parse_event_query_validates_range_limit_and_cursor():
    assert parse_event_query("") == ("24h", 12, None)
    assert parse_event_query("window=all&limit=24&before=123.5") == ("all", 24, 123.5)
    with pytest.raises(ValueError, match="window must be one of"):
        parse_event_query("window=month")
    with pytest.raises(ValueError, match="limit must be between"):
        parse_event_query("limit=200")
    with pytest.raises(ValueError, match="before must be a timestamp"):
        parse_event_query("before=yesterday")
    with pytest.raises(ValueError, match="before must be a positive timestamp"):
        parse_event_query("before=nan")


def test_with_query_preserves_existing_upstream_query():
    assert with_query("http://127.0.0.1:8080/stream?key=camera", "advance_headers=1") == (
        "http://127.0.0.1:8080/stream?key=camera&advance_headers=1"
    )


def test_same_origin_allows_direct_and_matching_requests():
    assert same_origin(None, "camera.example") is True
    assert same_origin("https://camera.example", "camera.example") is True
    assert same_origin("https://other.example", "camera.example") is False
    assert same_origin("null", "camera.example") is False


def test_dashboard_alert_policy_round_trip(tmp_path):
    settings = replace(
        dashboard_settings(tmp_path),
        policy_file=tmp_path / "alert-policy.json",
        timezone="Europe/Athens",
    )
    app = DashboardApplication(settings)

    assert app.alert_policy()["quiet_hours_enabled"] is False
    updated = app.update_alert_policy(
        {
            "quiet_hours_enabled": True,
            "quiet_hours_start": "23:00",
            "quiet_hours_end": "06:30",
        }
    )

    assert updated["quiet_hours_enabled"] is True
    assert updated["timezone"] == "Europe/Athens"
    assert app.alert_policy()["quiet_hours_start"] == "23:00"


def test_dashboard_motion_masks_round_trip(tmp_path):
    settings = replace(
        dashboard_settings(tmp_path),
        mask_file=tmp_path / "motion-masks.json",
    )
    app = DashboardApplication(settings)

    assert app.motion_masks()["regions"] == []
    updated = app.update_motion_masks(
        {"regions": [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}]}
    )

    assert updated["regions"] == [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}]
    assert app.motion_masks() == updated


def test_dashboard_webhook_test_hides_configured_url(monkeypatch, tmp_path):
    settings = replace(
        dashboard_settings(tmp_path),
        webhook_url="https://ha.example/api/webhook/secret-id",
    )
    app = DashboardApplication(settings)
    monkeypatch.setattr("pi_camera_sentinel.dashboard.deliver_webhook", lambda *_args, **_kwargs: 202)

    result = app.send_webhook_test()

    assert result == {"configured": True, "delivered": True, "status_code": 202}
    assert "secret-id" not in str(result)


def test_dashboard_services_include_feed_recovery(monkeypatch, tmp_path):
    settings = replace(
        dashboard_settings(tmp_path),
        motion_service="motion.service",
        recovery_service="recovery.service",
        exposure_service="exposure.service",
    )
    observed = []
    monkeypatch.setattr(
        "pi_camera_sentinel.dashboard.service_state",
        lambda name: observed.append(name) or {"name": name},
    )

    services = DashboardApplication(settings).services()

    assert list(services) == ["motion", "recovery", "watchdog"]
    assert observed == ["motion.service", "recovery.service", "exposure.service"]


def test_dashboard_manual_restart_returns_persisted_recovery_state(monkeypatch, tmp_path):
    settings = replace(
        dashboard_settings(tmp_path),
        stream_service="camera-stream.service",
    )
    app = DashboardApplication(settings)
    app._status = {"cached": True}
    observed = []
    restarted = RecoveryState(
        status="restarted",
        stream_service=settings.stream_service,
        restart_count=1,
        events=(
            RecoveryEvent(
                "stream_restarted",
                "2026-07-15T10:00:00+00:00",
                "Manual feed restart requested",
                "manual",
            ),
        ),
    )
    monkeypatch.setattr(
        "pi_camera_sentinel.dashboard.manual_restart_feed",
        lambda current_settings, state: observed.append((current_settings, state)) or restarted,
    )

    result = app.restart_feed()

    assert observed[0][0] is settings
    assert observed[0][1].stream_service == settings.stream_service
    assert result == restarted.to_dict()
    assert app._status is None


def test_dashboard_manual_restart_failure_invalidates_cached_status(monkeypatch, tmp_path):
    app = DashboardApplication(dashboard_settings(tmp_path))
    app._status = {"cached": True}

    def fail_restart(_settings, _state):
        raise OSError("restart failed")

    monkeypatch.setattr("pi_camera_sentinel.dashboard.manual_restart_feed", fail_restart)

    with pytest.raises(OSError, match="restart failed"):
        app.restart_feed()

    assert app._status is None
