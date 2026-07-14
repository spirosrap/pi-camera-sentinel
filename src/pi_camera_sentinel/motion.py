from __future__ import annotations

import io
from typing import Iterable

import requests
from PIL import Image, ImageChops, ImageDraw

from .config import Settings
from .masks import MotionMask


def fetch_snapshot(session: requests.Session, settings: Settings) -> tuple[bytes, Image.Image]:
    response = session.get(settings.snapshot_url, timeout=settings.http_timeout)
    response.raise_for_status()
    data = response.content
    image = Image.open(io.BytesIO(data))
    image.load()
    return data, image.convert("RGB")


def normalize_image(image: Image.Image, settings: Settings) -> Image.Image:
    return image.resize(
        (settings.resize_width, settings.resize_height),
        Image.Resampling.BILINEAR,
    ).convert("L")


def changed_pixel_ratio(
    previous: Image.Image,
    current: Image.Image,
    threshold: int,
    masks: Iterable[MotionMask] = (),
) -> float:
    if previous.size != current.size:
        raise ValueError(f"image sizes differ: {previous.size} != {current.size}")
    diff = ImageChops.difference(previous, current)
    regions = tuple(masks)
    if not regions:
        histogram = diff.histogram()
        active_pixels = previous.width * previous.height
    else:
        active_mask = Image.new("L", previous.size, color=255)
        draw = ImageDraw.Draw(active_mask)
        for region in regions:
            left, top, right, bottom = region.pixel_box(previous.width, previous.height)
            draw.rectangle((left, top, right - 1, bottom - 1), fill=0)
        histogram = diff.histogram(mask=active_mask)
        active_pixels = active_mask.histogram()[255]
        if active_pixels == 0:
            return 0.0
    changed = sum(count for value, count in enumerate(histogram) if value >= threshold)
    return changed / float(active_pixels)


def summarize_ratios(ratios: Iterable[float]) -> dict[str, float | int]:
    values = list(ratios)
    if not values:
        return {"frames_compared": 0}
    return {
        "frames_compared": len(values),
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
    }
