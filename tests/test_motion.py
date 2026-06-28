from PIL import Image

from pi_camera_sentinel.motion import changed_pixel_ratio, summarize_ratios


def test_changed_pixel_ratio_zero_for_identical_images():
    image = Image.new("L", (10, 10), color=10)

    assert changed_pixel_ratio(image, image, threshold=5) == 0


def test_changed_pixel_ratio_counts_threshold_pixels():
    previous = Image.new("L", (10, 10), color=0)
    current = Image.new("L", (10, 10), color=0)
    for x in range(5):
        current.putpixel((x, 0), 50)

    assert changed_pixel_ratio(previous, current, threshold=25) == 0.05


def test_summarize_ratios():
    summary = summarize_ratios([0.1, 0.2, 0.3])

    assert summary["frames_compared"] == 3
    assert summary["min"] == 0.1
    assert summary["max"] == 0.3
    assert round(summary["avg"], 3) == 0.2
