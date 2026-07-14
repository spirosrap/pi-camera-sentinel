import pytest

from pi_camera_sentinel.camera import (
    camera_state,
    detect_profile,
    parse_controls,
    set_controls,
    validate_control_values,
)


CONTROL_OUTPUT = """
                     brightness 0x00980900 (int)    : min=0 max=255 step=1 default=-8193 value=132
                       contrast 0x00980901 (int)    : min=0 max=255 step=1 default=57343 value=128
                     saturation 0x00980902 (int)    : min=0 max=255 step=1 default=57343 value=128
        white_balance_automatic 0x0098090c (bool)   : default=1 value=1
                           gain 0x00980913 (int)    : min=0 max=255 step=1 default=57343 value=20
           power_line_frequency 0x00980918 (menu)   : min=0 max=2 default=2 value=1 (50 Hz)
      white_balance_temperature 0x0098091a (int)    : min=2000 max=6500 step=1 default=57343 value=5619 flags=inactive
                      sharpness 0x0098091b (int)    : min=0 max=255 step=1 default=57343 value=128
         backlight_compensation 0x0098091c (int)    : min=0 max=1 step=1 default=57343 value=1
                  auto_exposure 0x009a0901 (menu)   : min=0 max=3 default=0 value=1 (Manual Mode)
         exposure_time_absolute 0x009a0902 (int)    : min=3 max=2047 step=1 default=250 value=19
"""


def test_parse_controls_reads_live_c920_format():
    controls = parse_controls(CONTROL_OUTPUT)

    assert controls["brightness"].value == 132
    assert controls["gain"].maximum == 255
    assert controls["white_balance_automatic"].minimum == 0
    assert controls["white_balance_automatic"].maximum == 1
    assert controls["white_balance_temperature"].inactive is True
    assert controls["auto_exposure"].menu_label == "Manual Mode"


def test_detect_profile_allows_camera_exposure_rounding():
    controls = parse_controls(CONTROL_OUTPUT)

    assert detect_profile(controls) == "low-light"


def test_camera_state_exposes_safe_ui_ranges(monkeypatch):
    controls = parse_controls(CONTROL_OUTPUT)
    monkeypatch.setattr("pi_camera_sentinel.camera.read_controls", lambda _device: controls)

    state = camera_state("/dev/video0")

    assert state["active_profile"] == "low-light"
    assert state["controls"]["gain"]["maximum"] == 255
    assert state["controls"]["gain"]["ui_maximum"] == 128
    assert state["controls"]["exposure_time_absolute"]["ui_maximum"] == 250


def test_validate_controls_rejects_unknown_and_extreme_values():
    controls = parse_controls(CONTROL_OUTPUT)

    with pytest.raises(ValueError, match="unsupported camera controls"):
        validate_control_values(controls, {"zoom_absolute": 200})
    with pytest.raises(ValueError, match="between 3 and 250"):
        validate_control_values(controls, {"exposure_time_absolute": 624})
    with pytest.raises(ValueError, match="one of: 1, 3"):
        validate_control_values(controls, {"auto_exposure": 2})


def test_validate_controls_activates_manual_dependencies():
    controls = parse_controls(CONTROL_OUTPUT)

    values = validate_control_values(
        controls,
        {
            "auto_exposure": 1,
            "exposure_time_absolute": 20,
            "white_balance_automatic": 0,
            "white_balance_temperature": 4500,
        },
    )

    assert values["exposure_time_absolute"] == 20
    assert values["white_balance_temperature"] == 4500


def test_set_controls_uses_dependency_order(monkeypatch):
    controls = parse_controls(CONTROL_OUTPUT)
    calls: list[str] = []
    monkeypatch.setattr("pi_camera_sentinel.camera.read_controls", lambda _device: controls)
    monkeypatch.setattr(
        "pi_camera_sentinel.camera.run_v4l2",
        lambda _device, args, timeout=10: calls.append(args[0]),
    )
    monkeypatch.setattr("pi_camera_sentinel.camera.camera_state", lambda device: {"device": device})

    result = set_controls(
        "/dev/video0",
        {"exposure_time_absolute": 20, "brightness": 134, "auto_exposure": 1},
    )

    assert calls == [
        "--set-ctrl=auto_exposure=1",
        "--set-ctrl=brightness=134",
        "--set-ctrl=exposure_time_absolute=20",
    ]
    assert result == {"device": "/dev/video0"}
