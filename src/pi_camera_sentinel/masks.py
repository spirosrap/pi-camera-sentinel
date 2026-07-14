from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


MAX_MOTION_MASKS = 8
MIN_MASK_SIZE = 0.01


@dataclass(frozen=True)
class MotionMask:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        for name in ("x", "y", "width", "height"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"motion mask {name} must be a finite number")
        if self.x < 0 or self.y < 0:
            raise ValueError("motion mask coordinates cannot be negative")
        if self.width < MIN_MASK_SIZE or self.height < MIN_MASK_SIZE:
            raise ValueError(f"motion mask width and height must be at least {MIN_MASK_SIZE}")
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("motion mask must fit inside the frame")

    @classmethod
    def from_dict(cls, payload: object) -> "MotionMask":
        if not isinstance(payload, dict):
            raise ValueError("each motion mask must be a JSON object")
        required = {"x", "y", "width", "height"}
        if not required.issubset(payload):
            raise ValueError("each motion mask requires x, y, width, and height")
        return cls(
            x=payload["x"],
            y=payload["y"],
            width=payload["width"],
            height=payload["height"],
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "x": round(float(self.x), 4),
            "y": round(float(self.y), 4),
            "width": round(float(self.width), 4),
            "height": round(float(self.height), 4),
        }

    def pixel_box(self, image_width: int, image_height: int) -> tuple[int, int, int, int]:
        left = max(0, min(image_width - 1, math.floor(self.x * image_width)))
        top = max(0, min(image_height - 1, math.floor(self.y * image_height)))
        right = max(left + 1, min(image_width, math.ceil(((self.x + self.width) * image_width) - 1e-9)))
        bottom = max(top + 1, min(image_height, math.ceil(((self.y + self.height) * image_height) - 1e-9)))
        return left, top, right, bottom


def validate_motion_masks(payload: object) -> tuple[MotionMask, ...]:
    if not isinstance(payload, list):
        raise ValueError("motion mask regions must be a JSON array")
    if len(payload) > MAX_MOTION_MASKS:
        raise ValueError(f"no more than {MAX_MOTION_MASKS} motion masks are allowed")
    return tuple(MotionMask.from_dict(region) for region in payload)


def load_motion_masks(path: Path) -> tuple[MotionMask, ...]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("motion mask file is not valid JSON") from exc
    if not isinstance(payload, dict) or "regions" not in payload:
        raise ValueError("motion mask file requires a regions array")
    return validate_motion_masks(payload["regions"])


def save_motion_masks(path: Path, masks: tuple[MotionMask, ...]) -> None:
    validated = validate_motion_masks([mask.to_dict() for mask in masks])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(
                {"regions": [mask.to_dict() for mask in validated]},
                handle,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o644)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
