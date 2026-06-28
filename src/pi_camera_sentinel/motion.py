from __future__ import annotations

import io
from typing import Iterable

import requests
from PIL import Image, ImageChops

from .config import Settings


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


def changed_pixel_ratio(previous: Image.Image, current: Image.Image, threshold: int) -> float:
    if previous.size != current.size:
        raise ValueError(f"image sizes differ: {previous.size} != {current.size}")
    diff = ImageChops.difference(previous, current)
    histogram = diff.histogram()
    changed = sum(count for value, count in enumerate(histogram) if value >= threshold)
    return changed / float(previous.width * previous.height)


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
