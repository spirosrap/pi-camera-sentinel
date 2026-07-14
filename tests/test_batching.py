import datetime as dt

import pytest

from pi_camera_sentinel.batching import MotionBatch, MotionSample, validate_batch_config


def sample(index: int, ratio: float) -> MotionSample:
    captured_at = dt.datetime(2026, 7, 14, 20, 0, index, tzinfo=dt.timezone.utc)
    return MotionSample(f"frame-{index}".encode(), ratio, captured_at)


def test_motion_batch_tracks_burst_and_keeps_latest_limited_frame():
    batch = MotionBatch.start(sample(0, 0.1), now=100.0, window_seconds=8.0, max_photos=3)

    batch.add(sample(1, 0.4))
    batch.add(sample(2, 0.2))
    batch.add(sample(3, 0.3))

    assert batch.detection_count == 4
    assert batch.peak_ratio == 0.4
    assert [item.snapshot for item in batch.samples] == [b"frame-0", b"frame-1", b"frame-3"]
    assert batch.first_captured_at == sample(0, 0.1).captured_at
    assert batch.last_captured_at == sample(3, 0.3).captured_at
    assert batch.duration_seconds == 3.0
    assert batch.due(107.99) is False
    assert batch.due(108.0) is True


@pytest.mark.parametrize(
    ("window_seconds", "max_photos"),
    [(-1, 4), (301, 4), (8, 0), (8, 11)],
)
def test_validate_batch_config_rejects_out_of_range_values(window_seconds, max_photos):
    with pytest.raises(ValueError):
        validate_batch_config(window_seconds, max_photos)


def test_validate_batch_config_accepts_immediate_and_album_modes():
    validate_batch_config(0, 1)
    validate_batch_config(300, 10)
