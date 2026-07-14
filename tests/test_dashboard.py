import io
import os
from dataclasses import replace

import requests
from PIL import Image

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.dashboard import collect_dashboard_status, list_recent_events, same_origin, with_query


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
    )


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
        undervoltage_seen=False,
        snapshot_get=lambda *_args, **_kwargs: response,
    )

    assert result["state"] == "online"
    assert result["ok"] is True
    assert result["title"] == "Garden camera"
    assert result["feed"]["width"] == 1280
    assert result["feed"]["height"] == 720
    assert result["feed"]["mean_luma"] == 120.0
    assert result["feed"]["dropped_frames"] == 0


def test_collect_dashboard_status_marks_undervoltage_as_degraded(tmp_path):
    response = FakeResponse(jpeg_bytes(), {"content-type": "image/jpeg"})

    result = collect_dashboard_status(
        dashboard_settings(tmp_path),
        undervoltage_seen=True,
        snapshot_get=lambda *_args, **_kwargs: response,
    )

    assert result["state"] == "degraded"
    assert result["system"]["undervoltage_seen"] is True
    assert any("undervoltage" in warning for warning in result["warnings"])


def test_collect_dashboard_status_marks_failed_snapshot_offline(tmp_path):
    def failed_snapshot(*_args, **_kwargs):
        raise requests.ConnectionError("camera stopped")

    result = collect_dashboard_status(
        dashboard_settings(tmp_path),
        undervoltage_seen=False,
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


def test_with_query_preserves_existing_upstream_query():
    assert with_query("http://127.0.0.1:8080/stream?key=camera", "advance_headers=1") == (
        "http://127.0.0.1:8080/stream?key=camera&advance_headers=1"
    )


def test_same_origin_allows_direct_and_matching_requests():
    assert same_origin(None, "camera.example") is True
    assert same_origin("https://camera.example", "camera.example") is True
    assert same_origin("https://other.example", "camera.example") is False
    assert same_origin("null", "camera.example") is False
