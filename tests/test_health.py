from dataclasses import replace
import subprocess

import pytest

from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.health import (
    check_health,
    parse_throttled_output,
    power_status_from_flags,
    read_current_power_status,
    read_throttle_flags,
)


class FakeResponse:
    ok = True
    status_code = 200
    headers = {"content-type": "image/jpeg"}


def test_parse_throttled_output_and_read_flags():
    observed = []

    def runner(command, **kwargs):
        observed.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "throttled=0x50005\n", "")

    assert parse_throttled_output("throttled=0x50005\n") == (0x50005, "0x50005")
    assert read_throttle_flags(which=lambda _name: "/usr/bin/vcgencmd", runner=runner) == (
        0x50005,
        "0x50005",
    )
    assert observed[0][0] == ["vcgencmd", "get_throttled"]
    with pytest.raises(ValueError, match="invalid vcgencmd"):
        parse_throttled_output("unexpected")


@pytest.mark.parametrize(
    ("flags", "recent", "expected"),
    [
        (0x50005, False, "active"),
        (0x50000, True, "recovered"),
        (0x50000, False, "historical"),
        (0, False, "stable"),
        (None, True, "recent"),
        (None, False, "unknown"),
    ],
)
def test_power_status_classifies_current_recent_and_historical(flags, recent, expected):
    throttle = None if flags is None else (flags, hex(flags))

    status = power_status_from_flags(throttle, recent)

    assert status.state == expected
    if flags == 0x50005:
        assert status.current_issues == ("Undervoltage", "CPU throttled")
        assert status.occurred_issues == ("Undervoltage", "CPU throttled")
        assert status.under_voltage_now is True
        assert status.throttled_now is True
        assert status.undervoltage_seen is True


def test_healthcheck_reports_disk_space(monkeypatch, tmp_path):
    settings = replace(
        Settings.from_env(),
        camera_device="auto",
        output_dir=tmp_path,
        disk_min_free_mb=0,
    )
    monkeypatch.setattr("pi_camera_sentinel.health.requests.get", lambda *_args, **_kwargs: FakeResponse())
    monkeypatch.setattr(
        "pi_camera_sentinel.health.read_power_status",
        lambda: power_status_from_flags((0, "0x0"), False),
    )

    result = check_health(settings)

    assert result.ok is True
    assert result.disk_path == str(tmp_path)
    assert result.disk_free_bytes > 0
    assert result.disk_total_bytes >= result.disk_free_bytes
    assert result.disk_low is False
    assert result.power.state == "stable"
    assert result.undervoltage_seen is False


def test_current_power_status_does_not_read_kernel_history(monkeypatch):
    monkeypatch.setattr(
        "pi_camera_sentinel.health.read_throttle_flags",
        lambda: (0x5, "0x5"),
    )
    monkeypatch.setattr(
        "pi_camera_sentinel.health.recent_undervoltage_seen",
        lambda: pytest.fail("current-only power status should not read logs"),
    )

    status = read_current_power_status()

    assert status.state == "active"
    assert status.current_issues == ("Undervoltage", "CPU throttled")
    assert status.recent_log_undervoltage is None
