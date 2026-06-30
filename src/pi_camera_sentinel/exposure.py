from __future__ import annotations

import io
import logging
import time
from dataclasses import asdict, dataclass

import requests
from PIL import Image, ImageStat

from .camera import apply_profile
from .config import Settings


LOG = logging.getLogger("pi-camera-sentinel.exposure")


@dataclass(frozen=True)
class ExposureStats:
    mean_rgb: list[float]
    mean_luma: float
    dark_ratio: float
    very_dark_ratio: float
    bright_ratio: float


@dataclass(frozen=True)
class ExposureDecision:
    decision: str
    before: ExposureStats
    after: ExposureStats

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "before": asdict(self.before),
            "after": asdict(self.after),
        }


def snapshot_exposure_stats(settings: Settings) -> ExposureStats:
    response = requests.get(settings.snapshot_url, timeout=settings.http_timeout)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content)).convert("RGB")
    stat = ImageStat.Stat(image)
    small = image.resize((settings.exposure_resize_width, settings.exposure_resize_height))
    pixels = list(small.getdata())
    dark_ratio = sum(1 for r, g, b in pixels if max(r, g, b) < settings.exposure_dark_pixel_max) / len(pixels)
    very_dark_ratio = sum(1 for r, g, b in pixels if max(r, g, b) < 8) / len(pixels)
    bright_ratio = sum(1 for r, g, b in pixels if max(r, g, b) > settings.exposure_bright_pixel_min) / len(pixels)
    mean_rgb = [round(channel, 2) for channel in stat.mean]
    mean_luma = round(sum(stat.mean) / 3.0, 2)
    return ExposureStats(
        mean_rgb=mean_rgb,
        mean_luma=mean_luma,
        dark_ratio=round(dark_ratio, 4),
        very_dark_ratio=round(very_dark_ratio, 4),
        bright_ratio=round(bright_ratio, 4),
    )


def choose_profile(settings: Settings, stats: ExposureStats) -> str:
    if stats.mean_luma >= settings.exposure_bright_mean_min or stats.bright_ratio >= settings.exposure_bright_ratio_min:
        return settings.exposure_day_profile
    if stats.mean_luma <= settings.exposure_dark_mean_max or stats.dark_ratio >= settings.exposure_dark_ratio_min:
        return settings.exposure_night_profile
    return "hold"


def exposure_watchdog_step(settings: Settings) -> ExposureDecision:
    before = snapshot_exposure_stats(settings)
    decision = choose_profile(settings, before)
    if decision != "hold":
        LOG.info("applying camera profile %s after exposure stats %s", decision, before)
        apply_profile(settings.camera_device, decision)
        time.sleep(settings.exposure_settle_seconds)
    after = snapshot_exposure_stats(settings) if decision != "hold" else before
    result = ExposureDecision(decision=decision, before=before, after=after)
    LOG.info("exposure decision=%s before=%s after=%s", decision, before, after)
    return result
