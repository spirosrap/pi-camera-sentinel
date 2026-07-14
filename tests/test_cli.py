import datetime as dt
from dataclasses import replace

import pytest
import requests

from pi_camera_sentinel import cli
from pi_camera_sentinel.batching import MotionBatch, MotionSample
from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.policy import AlertPolicy, save_alert_policy


def motion_settings(tmp_path) -> Settings:
    return replace(
        Settings.from_env(),
        output_dir=tmp_path / "events",
        policy_file=tmp_path / "alert-policy.json",
        timezone="Europe/Athens",
        send_photo=True,
        send_video=False,
        retention_files=10,
        webhook_url="",
    )


def test_quiet_hours_archive_without_sending(monkeypatch, tmp_path):
    settings = motion_settings(tmp_path)
    save_alert_policy(settings.policy_file, AlertPolicy(True, "00:00", "00:00"))
    monkeypatch.setattr(cli, "send_photo", lambda *_args, **_kwargs: pytest.fail("photo should be suppressed"))

    cli.handle_motion_event(settings, b"jpeg data", 0.25)

    assert len(list(settings.output_dir.glob("motion-*.jpg"))) == 1


def test_invalid_policy_fails_open_and_sends(monkeypatch, tmp_path):
    settings = motion_settings(tmp_path)
    settings.policy_file.write_text("invalid", encoding="utf-8")
    sent = []
    monkeypatch.setattr(cli, "send_photo", lambda *_args, **_kwargs: sent.append(True))

    cli.handle_motion_event(settings, b"jpeg data", 0.25)

    assert sent == [True]


def test_quiet_hours_still_deliver_home_assistant_webhook(monkeypatch, tmp_path):
    settings = replace(
        motion_settings(tmp_path),
        webhook_url="http://homeassistant.local/api/webhook/secret",
    )
    save_alert_policy(settings.policy_file, AlertPolicy(True, "00:00", "00:00"))
    delivered = []
    monkeypatch.setattr(cli, "send_photo", lambda *_args, **_kwargs: pytest.fail("photo should be suppressed"))
    monkeypatch.setattr(cli, "deliver_webhook", lambda _settings, payload: delivered.append(payload) or 200)

    cli.handle_motion_event(settings, b"jpeg data", 0.25)

    assert delivered[0]["event"] == "motion"
    assert delivered[0]["changed_ratio"] == 0.25


def test_webhook_failure_does_not_block_telegram(monkeypatch, tmp_path):
    settings = replace(
        motion_settings(tmp_path),
        webhook_url="http://homeassistant.local/api/webhook/secret",
    )
    sent = []
    monkeypatch.setattr(cli, "send_photo", lambda *_args, **_kwargs: sent.append(True))
    monkeypatch.setattr(
        cli,
        "deliver_webhook",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.ConnectionError("offline")),
    )

    cli.handle_motion_event(settings, b"jpeg data", 0.25)

    assert sent == [True]
    assert len(list(settings.output_dir.glob("motion-*.jpg"))) == 1


def test_motion_batch_sends_album_and_webhook_summary(monkeypatch, tmp_path):
    settings = replace(
        motion_settings(tmp_path),
        webhook_url="http://homeassistant.local/api/webhook/secret",
    )
    captured_at = dt.datetime(2026, 7, 14, 20, 0, tzinfo=dt.timezone.utc)
    batch = MotionBatch.start(
        MotionSample(b"first", 0.1, captured_at),
        now=100,
        window_seconds=8,
        max_photos=4,
    )
    batch.add(MotionSample(b"second", 0.4, captured_at + dt.timedelta(seconds=2)))
    batch.add(MotionSample(b"third", 0.2, captured_at + dt.timedelta(seconds=5)))
    albums = []
    webhooks = []
    monkeypatch.setattr(cli, "send_photo", lambda *_args: pytest.fail("album expected"))
    monkeypatch.setattr(
        cli,
        "send_media_group",
        lambda _settings, paths, text: albums.append((paths, text)),
    )
    monkeypatch.setattr(
        cli,
        "deliver_webhook",
        lambda _settings, payload: webhooks.append(payload) or 202,
    )

    cli.handle_motion_batch(settings, batch)

    paths, text = albums[0]
    assert [path.read_bytes() for path in paths] == [b"first", b"second", b"third"]
    assert "Motion burst: 3 detections over 5s" in text
    assert webhooks[0]["changed_ratio"] == 0.4
    assert webhooks[0]["batch"]["detection_count"] == 3
    assert webhooks[0]["batch"]["photo_count"] == 3
    assert len(webhooks[0]["batch"]["event_urls"]) == 3


def test_send_webhook_test_reports_status_without_url(monkeypatch, capsys):
    settings = replace(
        Settings.from_env(),
        webhook_url="http://homeassistant.local/api/webhook/secret",
    )
    monkeypatch.setattr(cli, "deliver_webhook", lambda *_args, **_kwargs: 204)

    assert cli.cmd_send_webhook_test(settings, None) == 0
    output = capsys.readouterr().out
    assert '"status_code": 204' in output
    assert "secret" not in output
