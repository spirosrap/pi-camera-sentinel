from dataclasses import replace

import pytest

from pi_camera_sentinel import cli
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
