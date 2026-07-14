import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.webhook import (
    deliver_webhook,
    event_capture_url,
    validate_webhook_url,
    webhook_payload,
)


class FakeResponse:
    status_code = 202

    def raise_for_status(self) -> None:
        return None


def webhook_settings() -> Settings:
    return replace(
        Settings.from_env(),
        webhook_url="http://homeassistant.local:8123/api/webhook/secret-id",
        webhook_timeout=3.5,
        feed_url="https://camera.example/stream",
        dashboard_title="Garden camera",
    )


def test_validate_webhook_url_accepts_local_http_and_rejects_invalid_urls():
    assert validate_webhook_url("http://homeassistant.local:8123/api/webhook/id")
    assert validate_webhook_url("https://ha.example/api/webhook/id")
    with pytest.raises(ValueError, match="not configured"):
        validate_webhook_url("")
    with pytest.raises(ValueError, match="http or https"):
        validate_webhook_url("file:///tmp/event")
    with pytest.raises(ValueError, match="fragment"):
        validate_webhook_url("https://ha.example/api/webhook/id#secret")


def test_event_capture_url_uses_dashboard_event_route():
    assert event_capture_url("https://camera.example/stream", "motion one.jpg") == (
        "https://camera.example/events/motion%20one.jpg"
    )
    assert event_capture_url("", "motion.jpg") is None
    assert event_capture_url("https://camera.example/", None) is None


def test_webhook_payload_contains_motion_context_without_secret_url(monkeypatch):
    monkeypatch.setattr("pi_camera_sentinel.webhook.socket.gethostname", lambda: "pi-camera")
    payload = webhook_payload(
        webhook_settings(),
        event="motion",
        captured_at=dt.datetime(2026, 7, 14, 20, 0, tzinfo=dt.timezone.utc),
        ratio=0.1234567,
        capture_path=Path("motion-20260714-200000.jpg"),
    )

    assert payload == {
        "event": "motion",
        "source": "pi-camera-sentinel",
        "camera": "Garden camera",
        "hostname": "pi-camera",
        "captured_at": "2026-07-14T20:00:00+00:00",
        "changed_ratio": 0.123457,
        "capture": "motion-20260714-200000.jpg",
        "event_url": "https://camera.example/events/motion-20260714-200000.jpg",
        "feed_url": "https://camera.example/stream",
    }
    assert "secret-id" not in str(payload)


def test_deliver_webhook_posts_json_with_timeout():
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    status_code = deliver_webhook(webhook_settings(), {"event": "test"}, post=fake_post)

    assert status_code == 202
    assert calls == [
        (
            "http://homeassistant.local:8123/api/webhook/secret-id",
            {
                "json": {"event": "test"},
                "timeout": 3.5,
                "headers": {"User-Agent": "pi-camera-sentinel"},
            },
        )
    ]
