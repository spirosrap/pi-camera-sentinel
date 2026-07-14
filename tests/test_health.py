from dataclasses import replace

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.health import check_health


class FakeResponse:
    ok = True
    status_code = 200
    headers = {"content-type": "image/jpeg"}


def test_healthcheck_reports_disk_space(monkeypatch, tmp_path):
    settings = replace(
        Settings.from_env(),
        camera_device="auto",
        output_dir=tmp_path,
        disk_min_free_mb=0,
    )
    monkeypatch.setattr("pi_camera_sentinel.health.requests.get", lambda *_args, **_kwargs: FakeResponse())
    monkeypatch.setattr("pi_camera_sentinel.health.recent_undervoltage_seen", lambda: False)

    result = check_health(settings)

    assert result.ok is True
    assert result.disk_path == str(tmp_path)
    assert result.disk_free_bytes > 0
    assert result.disk_total_bytes >= result.disk_free_bytes
    assert result.disk_low is False
