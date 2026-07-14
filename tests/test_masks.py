import json

import pytest

from pi_camera_sentinel.masks import (
    MAX_MOTION_MASKS,
    MotionMask,
    load_motion_masks,
    save_motion_masks,
    validate_motion_masks,
)


def test_motion_mask_validates_normalized_geometry():
    mask = MotionMask(x=0.1, y=0.2, width=0.3, height=0.4)

    assert mask.to_dict() == {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
    assert mask.pixel_box(160, 90) == (16, 18, 64, 54)

    with pytest.raises(ValueError, match="fit inside"):
        MotionMask(x=0.8, y=0, width=0.3, height=0.2)
    with pytest.raises(ValueError, match="at least"):
        MotionMask(x=0, y=0, width=0.001, height=0.2)


def test_validate_motion_masks_rejects_invalid_payloads():
    with pytest.raises(ValueError, match="JSON array"):
        validate_motion_masks({})
    with pytest.raises(ValueError, match=f"no more than {MAX_MOTION_MASKS}"):
        validate_motion_masks(
            [{"x": 0, "y": 0, "width": 0.1, "height": 0.1}] * (MAX_MOTION_MASKS + 1)
        )
    with pytest.raises(ValueError, match="finite number"):
        validate_motion_masks([{"x": "left", "y": 0, "width": 0.1, "height": 0.1}])


def test_motion_mask_file_round_trip_is_atomic(tmp_path):
    path = tmp_path / "motion-masks.json"
    masks = (MotionMask(x=0.125, y=0.25, width=0.3, height=0.4),)

    assert load_motion_masks(path) == ()
    save_motion_masks(path, masks)

    assert load_motion_masks(path) == masks
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "regions": [{"x": 0.125, "y": 0.25, "width": 0.3, "height": 0.4}]
    }
    assert list(tmp_path.glob(".motion-masks.json.*")) == []


def test_motion_mask_file_rejects_invalid_json(tmp_path):
    path = tmp_path / "motion-masks.json"
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        load_motion_masks(path)
