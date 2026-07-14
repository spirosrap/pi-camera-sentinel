from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


MAX_TELEGRAM_ALBUM_PHOTOS = 10
MAX_ALERT_BATCH_SECONDS = 300.0


@dataclass(frozen=True)
class MotionSample:
    snapshot: bytes
    ratio: float
    captured_at: dt.datetime


@dataclass
class MotionBatch:
    started_monotonic: float
    deadline_monotonic: float
    max_photos: int
    samples: list[MotionSample] = field(default_factory=list)
    detection_count: int = 0
    peak_ratio: float = 0.0
    first_captured_at: dt.datetime | None = None
    last_captured_at: dt.datetime | None = None

    @classmethod
    def start(
        cls,
        sample: MotionSample,
        *,
        now: float,
        window_seconds: float,
        max_photos: int,
    ) -> "MotionBatch":
        batch = cls(
            started_monotonic=now,
            deadline_monotonic=now + window_seconds,
            max_photos=max_photos,
        )
        batch.add(sample)
        return batch

    def add(self, sample: MotionSample) -> None:
        self.detection_count += 1
        self.peak_ratio = max(self.peak_ratio, sample.ratio)
        if self.first_captured_at is None:
            self.first_captured_at = sample.captured_at
        self.last_captured_at = sample.captured_at

        if len(self.samples) < self.max_photos:
            self.samples.append(sample)
        else:
            self.samples[-1] = sample

    def due(self, now: float) -> bool:
        return now >= self.deadline_monotonic

    @property
    def duration_seconds(self) -> float:
        if self.first_captured_at is None or self.last_captured_at is None:
            return 0.0
        return max(0.0, (self.last_captured_at - self.first_captured_at).total_seconds())


def validate_batch_config(window_seconds: float, max_photos: int) -> None:
    if window_seconds < 0 or window_seconds > MAX_ALERT_BATCH_SECONDS:
        raise ValueError(
            f"alert batch window must be between 0 and {MAX_ALERT_BATCH_SECONDS:g} seconds"
        )
    if max_photos < 1 or max_photos > MAX_TELEGRAM_ALBUM_PHOTOS:
        raise ValueError(
            f"alert batch photo limit must be between 1 and {MAX_TELEGRAM_ALBUM_PHOTOS}"
        )
