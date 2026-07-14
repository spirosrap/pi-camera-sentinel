import datetime as dt

import pytest

from pi_camera_sentinel.policy import AlertPolicy, load_alert_policy, save_alert_policy


ATHENS = "Europe/Athens"


def athens_time(hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 7, 14, hour, minute, tzinfo=dt.timezone(dt.timedelta(hours=3)))


def test_overnight_quiet_hours_cross_midnight():
    policy = AlertPolicy(True, "22:00", "07:00")

    assert policy.quiet_now(ATHENS, athens_time(23)) is True
    assert policy.quiet_now(ATHENS, athens_time(6, 59)) is True
    assert policy.quiet_now(ATHENS, athens_time(7)) is False
    assert policy.quiet_now(ATHENS, athens_time(21, 59)) is False


def test_daytime_and_all_day_quiet_hours():
    daytime = AlertPolicy(True, "09:00", "17:00")
    all_day = AlertPolicy(True, "00:00", "00:00")

    assert daytime.quiet_now(ATHENS, athens_time(12)) is True
    assert daytime.quiet_now(ATHENS, athens_time(18)) is False
    assert all_day.quiet_now(ATHENS, athens_time(12)) is True
    assert AlertPolicy(False, "00:00", "00:00").quiet_now(ATHENS, athens_time(12)) is False


def test_policy_validates_times_and_timezone():
    with pytest.raises(ValueError, match="HH:MM"):
        AlertPolicy(True, "7:00", "22:00")
    with pytest.raises(ValueError, match="unknown timezone"):
        AlertPolicy().to_dict("Mars/Olympus")


def test_policy_round_trip_is_atomic_and_defaults_when_missing(tmp_path):
    path = tmp_path / "state" / "alert-policy.json"
    assert load_alert_policy(path) == AlertPolicy()

    expected = AlertPolicy(True, "23:30", "06:15")
    save_alert_policy(path, expected)

    assert load_alert_policy(path) == expected
    assert path.stat().st_mode & 0o777 == 0o644
    assert list(path.parent.glob(f".{path.name}.*")) == []


def test_invalid_policy_file_does_not_silently_default(tmp_path):
    path = tmp_path / "alert-policy.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        load_alert_policy(path)
