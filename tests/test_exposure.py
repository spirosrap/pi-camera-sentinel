from pi_camera_sentinel.config import Settings
from pi_camera_sentinel.exposure import ExposureStats, choose_profile


def settings() -> Settings:
    return Settings.from_env()


def test_choose_day_profile_for_washed_out_frame():
    stats = ExposureStats(
        mean_rgb=[255, 255, 255],
        mean_luma=255,
        dark_ratio=0,
        very_dark_ratio=0,
        bright_ratio=1,
    )

    assert choose_profile(settings(), stats) == "auto"


def test_choose_night_profile_for_black_frame():
    stats = ExposureStats(
        mean_rgb=[0, 0, 0],
        mean_luma=0,
        dark_ratio=1,
        very_dark_ratio=1,
        bright_ratio=0,
    )

    assert choose_profile(settings(), stats) == "low-light"


def test_choose_hold_for_normal_frame():
    stats = ExposureStats(
        mean_rgb=[120, 120, 120],
        mean_luma=120,
        dark_ratio=0.01,
        very_dark_ratio=0,
        bright_ratio=0.10,
    )

    assert choose_profile(settings(), stats) == "hold"
