import gzip
import io
import os
import threading
import time
from dataclasses import replace

import pytest
import requests
from PIL import Image

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.dashboard import (
    DashboardApplication,
    DashboardHTTPServer,
    DashboardRequestHandler,
    accepts_gzip,
    collect_dashboard_status,
    event_history,
    event_thumbnail_bytes,
    list_recent_events,
    parse_event_query,
    same_origin,
    static_file_bytes,
    with_query,
)
from pi_camera_sentinel.health import power_status_from_flags
from pi_camera_sentinel.health_alerts import (
    HealthAlertState,
    HealthIssue,
    HealthIssueTracker,
    save_health_alert_state,
)
from pi_camera_sentinel.recovery import RecoveryEvent, RecoveryState
from pi_camera_sentinel.retention import RetentionPolicy, archive_files as read_archive_files


class FakeResponse:
    def __init__(self, content: bytes, headers: dict[str, str], status_code: int = 200):
        self.content = content
        self.headers = headers
        self.status_code = status_code
        self.closed = False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def close(self) -> None:
        self.closed = True


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
        health_state_file=tmp_path / "health-alert-state.json",
    )


def power_status(flags: int = 0, recent: bool = False):
    return power_status_from_flags((flags, hex(flags)), recent)


@pytest.fixture
def dashboard_server(tmp_path):
    settings = dashboard_settings(tmp_path)
    server = DashboardHTTPServer(("127.0.0.1", 0), DashboardApplication(settings))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", settings
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


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
    assert result["feed"]["stale"] is False
    assert result["automation"]["alert_batching"] == {
        "enabled": True,
        "window_seconds": 8.0,
        "max_photos": 4,
    }
    assert result["automation"]["feed_recovery"]["state"]["status"] == "unknown"
    assert result["automation"]["feed_recovery"]["failure_threshold"] == 3
    assert result["automation"]["feed_recovery"]["telegram_alerts"] is False
    assert result["automation"]["health_alerts"]["telegram_alerts"] is False
    assert result["automation"]["health_alerts"]["state"]["initialized"] is False
    assert result["integrations"]["home_assistant"]["configured"] is False


def test_collect_dashboard_status_reuses_recent_frame_metrics(monkeypatch, tmp_path):
    response = FakeResponse(
        b"already validated by the previous sample",
        {
            "content-type": "image/jpeg",
            "x-ustreamer-width": "1280",
            "x-ustreamer-height": "720",
            "x-ustreamer-online": "true",
        },
    )
    def fail_open(*_args, **_kwargs):
        raise AssertionError("unexpected decode")

    monkeypatch.setattr("pi_camera_sentinel.dashboard.Image.open", fail_open)
    observed = {}

    def read_snapshot(*_args, **kwargs):
        observed.update(kwargs)
        return response

    result = collect_dashboard_status(
        dashboard_settings(tmp_path),
        power_status=power_status(),
        snapshot_get=read_snapshot,
        cached_frame_metrics=(1280, 720, 137.5),
        sample_luma=False,
    )

    assert result["feed"]["width"] == 1280
    assert result["feed"]["height"] == 720
    assert result["feed"]["mean_luma"] == 137.5
    assert result["feed"]["online"] is True
    assert observed["stream"] is True
    assert response.closed is True


def test_dashboard_status_refreshes_stale_luma_off_request_thread(monkeypatch, tmp_path):
    app = DashboardApplication(dashboard_settings(tmp_path))
    app._frame_metrics = (1280, 720, 111.0)
    app._frame_metrics_at = time.monotonic() - 31.0
    app._power = power_status()
    app._power_at = time.monotonic()
    observed = []
    scheduled = []

    def collect(_settings, **kwargs):
        observed.append(kwargs)
        return {
            "feed": {
                "ok": True,
                "width": 1280,
                "height": 720,
                "mean_luma": 111.0,
            }
        }

    monkeypatch.setattr("pi_camera_sentinel.dashboard.collect_dashboard_status", collect)
    monkeypatch.setattr(app, "_schedule_frame_metrics_refresh", lambda: scheduled.append(True))

    result = app.status()

    assert result["feed"]["mean_luma"] == 111.0
    assert observed[0]["sample_luma"] is False
    assert observed[0]["cached_frame_metrics"] == (1280, 720, 111.0)
    assert scheduled == [True]


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


def test_dashboard_status_reports_configured_recovery_telegram_alerts(tmp_path):
    settings = replace(
        dashboard_settings(tmp_path),
        recovery_telegram_alerts=True,
        telegram_token="token",
        telegram_chat_id="123",
    )

    result = collect_dashboard_status(
        settings,
        power_status=power_status(),
        snapshot_get=lambda *_args, **_kwargs: FakeResponse(
            jpeg_bytes(),
            {"content-type": "image/jpeg"},
        ),
    )

    assert result["automation"]["feed_recovery"]["telegram_alerts"] is True


def test_dashboard_status_reports_active_system_health_alerts(tmp_path):
    settings = replace(
        dashboard_settings(tmp_path),
        health_telegram_alerts=True,
        telegram_token="token",
        telegram_chat_id="123",
    )
    save_health_alert_state(
        settings.health_state_file,
        HealthAlertState(
            initialized=True,
            trackers=(
                HealthIssueTracker(
                    issue=HealthIssue("power", "Power", "Undervoltage"),
                    active=True,
                ),
            ),
        ),
    )

    result = collect_dashboard_status(
        settings,
        power_status=power_status(),
        snapshot_get=lambda *_args, **_kwargs: FakeResponse(
            jpeg_bytes(),
            {"content-type": "image/jpeg"},
        ),
    )

    health_alerts = result["automation"]["health_alerts"]
    assert health_alerts["telegram_alerts"] is True
    assert health_alerts["state"]["trackers"][0]["issue"]["key"] == "power"


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


def test_collect_dashboard_status_marks_old_frame_offline(monkeypatch, tmp_path):
    response = FakeResponse(
        jpeg_bytes(),
        {
            "content-type": "image/jpeg",
            "x-timestamp": "100.0",
            "x-ustreamer-online": "true",
        },
    )
    settings = replace(dashboard_settings(tmp_path), recovery_stale_seconds=20)
    monkeypatch.setattr("pi_camera_sentinel.dashboard.time.time", lambda: 125.5)

    result = collect_dashboard_status(
        settings,
        power_status=power_status(),
        snapshot_get=lambda *_args, **_kwargs: response,
    )

    assert result["state"] == "offline"
    assert result["ok"] is False
    assert result["feed"]["online"] is True
    assert result["feed"]["stale"] is True
    assert result["feed"]["frame_age_seconds"] == 25.5
    assert "camera frame is older than 20 seconds" in result["warnings"]


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
    assert events[0]["thumbnail_url"].startswith("/events/thumbnails/motion-newer.jpg?v=")
    assert events[0]["thumbnail_url"].endswith("-2")


def test_event_thumbnail_is_small_bounded_jpeg(tmp_path):
    source = tmp_path / "motion-thumbnail.jpg"
    source.write_bytes(jpeg_bytes((40, 120, 200)))
    stat = source.stat()

    thumbnail = event_thumbnail_bytes(str(source), stat.st_mtime_ns, stat.st_size)

    with Image.open(io.BytesIO(thumbnail)) as image:
        assert image.format == "JPEG"
        assert image.size == (320, 180)
    assert len(thumbnail) < stat.st_size


def test_static_file_bytes_caches_compressed_representation(tmp_path):
    source = tmp_path / "asset.js"
    source.write_bytes(b"const value = 1;\n" * 100)
    stat = source.stat()
    static_file_bytes.cache_clear()

    first = static_file_bytes(str(source), stat.st_mtime_ns, stat.st_size, True)
    before = static_file_bytes.cache_info()
    second = static_file_bytes(str(source), stat.st_mtime_ns, stat.st_size, True)
    after = static_file_bytes.cache_info()

    assert gzip.decompress(first) == source.read_bytes()
    assert second is first
    assert after.hits == before.hits + 1


def test_accepts_gzip_honors_explicit_quality():
    assert accepts_gzip("br, gzip") is True
    assert accepts_gzip("*;q=0.5") is True
    assert accepts_gzip("gzip;q=0, *;q=1") is False
    assert accepts_gzip(None) is False


def test_static_assets_are_compressed_and_conditionally_cached(dashboard_server):
    base_url, _settings = dashboard_server

    response = requests.get(
        f"{base_url}/assets/app.js?v=test",
        headers={"Accept-Encoding": "gzip"},
        timeout=2,
    )

    assert response.status_code == 200
    assert response.headers["Content-Encoding"] == "gzip"
    assert "immutable" in response.headers["Cache-Control"]
    assert response.headers["Server-Timing"].startswith("app;dur=")
    etag = response.headers["ETag"]

    cached = requests.get(
        f"{base_url}/assets/app.js?v=test",
        headers={"Accept-Encoding": "gzip", "If-None-Match": etag},
        timeout=2,
    )

    assert cached.status_code == 304
    assert cached.content == b""


def test_motion_zone_editor_is_a_dedicated_no_cache_page(dashboard_server):
    base_url, _settings = dashboard_server

    dashboard = requests.get(f"{base_url}/", timeout=2)
    editor = requests.get(f"{base_url}/motion-zones", timeout=2)

    assert dashboard.status_code == 200
    assert "img-src 'self' data: blob:" in dashboard.headers["Content-Security-Policy"]
    assert 'href="/motion-zones"' in dashboard.text
    assert 'id="motion-mask-canvas"' not in dashboard.text
    assert editor.status_code == 200
    assert editor.headers["Cache-Control"] == "no-cache"
    assert "Ignored areas" in editor.text
    assert "Still frame" in editor.text
    assert 'id="motion-mask-canvas"' in editor.text
    assert 'id="camera-stream"' not in editor.text


def test_dashboard_stream_has_a_latest_frame_fallback(dashboard_server):
    base_url, _settings = dashboard_server

    dashboard = requests.get(f"{base_url}/", timeout=2)
    script = requests.get(f"{base_url}/assets/app.js?v=test", timeout=2)

    assert dashboard.status_code == 200
    assert 'id="camera-fallback"' in dashboard.text
    assert 'data-client-version="1.17.0"' in dashboard.text
    assert '<canvas class="stream-live" id="camera-stream"' in dashboard.text
    assert 'data-has-frame="false"' in dashboard.text
    assert "function inspectStreamHealth()" in script.text
    assert "async function consumeStream(" in script.text
    assert "async function consumeSnapshotStream(" in script.text
    assert "function extractStreamFrames(" in script.text
    assert "function updateReconnectNotice(" in script.text
    assert "const streamFailureThreshold = 3;" in script.text
    assert "function reconcileClientVersion(" in script.text
    assert 'target.searchParams.set("sentinel_version", serverVersion);' in script.text
    assert "refreshStreamFallback();" in script.text
    assert "Latest frame retained / waiting for camera" in script.text


def test_client_disconnect_is_not_reclassified_as_policy_failure():
    handler = object.__new__(DashboardRequestHandler)

    class App:
        @staticmethod
        def alert_policy():
            return {"quiet_hours_enabled": False}

    class Server:
        app = App()

    handler.server = Server()
    sends = []

    def disconnect(*args, **kwargs):
        sends.append((args, kwargs))
        raise BrokenPipeError("browser left")

    handler.send_json = disconnect

    with pytest.raises(BrokenPipeError, match="browser left"):
        handler.send_policy_state()

    assert len(sends) == 1


def test_thumbnail_route_serves_cached_preview(dashboard_server):
    base_url, settings = dashboard_server
    source = settings.output_dir / "motion-route.jpg"
    source.write_bytes(jpeg_bytes((20, 80, 140)))

    response = requests.get(
        f"{base_url}/events/thumbnails/{source.name}",
        timeout=2,
    )

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/jpeg"
    assert "immutable" in response.headers["Cache-Control"]
    assert len(response.content) < source.stat().st_size
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (320, 180)


def test_dashboard_coalesces_duplicate_thumbnail_work(monkeypatch, tmp_path):
    source = tmp_path / "motion-shared.jpg"
    source.write_bytes(jpeg_bytes())
    stat = source.stat()
    app = DashboardApplication(dashboard_settings(tmp_path))
    calls = []
    started = threading.Event()
    release = threading.Event()

    def generate(*key):
        calls.append(key)
        started.set()
        assert release.wait(timeout=1)
        return b"thumbnail"

    monkeypatch.setattr("pi_camera_sentinel.dashboard.event_thumbnail_bytes", generate)
    results = []
    workers = [
        threading.Thread(target=lambda: results.append(app.event_thumbnail(source, stat)))
        for _ in range(2)
    ]
    try:
        for worker in workers:
            worker.start()
        assert started.wait(timeout=1)
        time.sleep(0.05)
        release.set()
        for worker in workers:
            worker.join(timeout=1)
    finally:
        release.set()
        app.close()

    assert results == [b"thumbnail", b"thumbnail"]
    assert len(calls) == 1


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
    activity = first_page["activity"]
    assert len(activity["buckets"]) == 24
    assert sum(bucket["count"] for bucket in activity["buckets"]) == 2
    assert activity["peak_count"] == 2
    assert activity["active_bucket_count"] == 1
    assert activity["last_captured_at"] == "1970-01-24T03:32:20+00:00"

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


def test_event_activity_places_boundaries_and_adapts_all_range(tmp_path):
    now = 10_000_000.0
    timestamps = [
        now - (30 * 60),
        now - (90 * 60),
        now - (24 * 60 * 60),
        now - (45 * 24 * 60 * 60),
    ]
    for index, timestamp in enumerate(timestamps):
        path = tmp_path / f"motion-activity-{index}.jpg"
        path.write_bytes(b"x" * (index + 1))
        os.utime(path, (timestamp, timestamp))

    daily = event_history(tmp_path, window="24h", now=now)["activity"]
    assert len(daily["buckets"]) == 24
    assert sum(bucket["count"] for bucket in daily["buckets"]) == 3
    assert daily["active_bucket_count"] == 3
    assert daily["peak_count"] == 1
    assert daily["peak_started_at"] == daily["buckets"][-1]["started_at"]

    complete = event_history(tmp_path, window="all", now=now)["activity"]
    assert complete["bucket_seconds"] == 4 * 24 * 60 * 60
    assert len(complete["buckets"]) == 12
    assert sum(bucket["count"] for bucket in complete["buckets"]) == 4


def test_event_history_filters_and_paginates_selected_period(tmp_path):
    now = 2_000_000.0
    timestamps = [now - 10, now - 20, now - 30, now - 100]
    for index, timestamp in enumerate(timestamps):
        path = tmp_path / f"motion-period-{index}.jpg"
        path.write_bytes(b"x" * (index + 1))
        os.utime(path, (timestamp, timestamp))

    first_page = event_history(
        tmp_path,
        window="24h",
        limit=1,
        period_start=now - 30,
        period_end=now - 10,
        now=now,
    )

    assert [event["name"] for event in first_page["events"]] == ["motion-period-1.jpg"]
    assert first_page["selection"] == {
        "started_at": "1970-01-24T03:32:50+00:00",
        "ended_at": "1970-01-24T03:33:10+00:00",
        "count": 2,
        "size_bytes": 5,
    }
    assert first_page["next_before"] == timestamps[1]
    assert first_page["summary"]["window_count"] == 4
    assert sum(bucket["count"] for bucket in first_page["activity"]["buckets"]) == 4

    second_page = event_history(
        tmp_path,
        window="24h",
        limit=1,
        before=first_page["next_before"],
        period_start=now - 30,
        period_end=now - 10,
        now=now,
    )
    assert [event["name"] for event in second_page["events"]] == ["motion-period-2.jpg"]
    assert second_page["next_before"] is None


def test_empty_event_activity_uses_stable_single_all_bucket(tmp_path):
    activity = event_history(tmp_path, window="all", now=10_000_000.0)["activity"]

    assert activity["active_bucket_count"] == 0
    assert activity["peak_count"] == 0
    assert activity["peak_started_at"] is None
    assert activity["last_captured_at"] is None
    assert len(activity["buckets"]) == 1


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
    assert parse_event_query("") == ("24h", 12, None, None, None)
    assert parse_event_query(
        "window=all&limit=24&before=123.5&period_start=100&period_end=200"
    ) == ("all", 24, 123.5, 100.0, 200.0)
    with pytest.raises(ValueError, match="window must be one of"):
        parse_event_query("window=month")
    with pytest.raises(ValueError, match="limit must be between"):
        parse_event_query("limit=200")
    with pytest.raises(ValueError, match="before must be a timestamp"):
        parse_event_query("before=yesterday")
    with pytest.raises(ValueError, match="before must be a positive timestamp"):
        parse_event_query("before=nan")
    with pytest.raises(ValueError, match="provided together"):
        parse_event_query("period_start=100")
    with pytest.raises(ValueError, match="period boundaries must be timestamps"):
        parse_event_query("period_start=yesterday&period_end=200")
    with pytest.raises(ValueError, match="period boundaries must be positive timestamps"):
        parse_event_query("period_start=100&period_end=nan")
    with pytest.raises(ValueError, match="period_start must be earlier"):
        parse_event_query("period_start=200&period_end=100")


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
        health_service="health.service",
        exposure_service="exposure.service",
    )
    observed = []

    def read_states(names):
        batch = tuple(names)
        observed.append(batch)
        return {name: {"name": name} for name in batch}

    monkeypatch.setattr(
        "pi_camera_sentinel.dashboard.service_states",
        read_states,
    )

    app = DashboardApplication(settings)
    services = app.services()
    assert app.services() is services

    assert list(services) == ["motion", "recovery", "health", "watchdog"]
    assert observed == [
        (
            "motion.service",
            "recovery.service",
            "health.service",
            "exposure.service",
        )
    ]

    scheduled = []
    app._services_at = time.monotonic() - 6.0
    monkeypatch.setattr(app, "_schedule_service_refresh", lambda: scheduled.append(True))

    assert app.services() is services
    assert scheduled == [True]
    assert len(observed) == 1


def test_dashboard_reuses_archive_scan_until_directory_changes(monkeypatch, tmp_path):
    first = tmp_path / "motion-first.jpg"
    first.write_bytes(b"first")
    os.utime(tmp_path, (100, 100))
    scans = []

    def scan(directory):
        scans.append(directory)
        return read_archive_files(directory)

    monkeypatch.setattr("pi_camera_sentinel.dashboard.archive_files", scan)
    app = DashboardApplication(dashboard_settings(tmp_path))

    first_result = app.events(
        window="all",
        limit=12,
        before=None,
        period_start=None,
        period_end=None,
    )
    second_result = app.events(
        window="all",
        limit=12,
        before=None,
        period_start=None,
        period_end=None,
    )
    assert first_result["summary"]["retained_count"] == 1
    assert second_result["summary"]["retained_count"] == 1
    assert second_result is first_result
    assert len(scans) == 1

    (tmp_path / "motion-second.jpg").write_bytes(b"second")
    os.utime(tmp_path, (200, 200))
    changed = app.events(
        window="all",
        limit=12,
        before=None,
        period_start=None,
        period_end=None,
    )

    assert changed["summary"]["retained_count"] == 2
    assert changed is not first_result
    assert len(scans) == 2


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
