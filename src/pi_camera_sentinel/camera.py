from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraProfile:
    name: str
    label: str
    controls: dict[str, int]


@dataclass(frozen=True)
class CameraControl:
    name: str
    kind: str
    minimum: int
    maximum: int
    step: int
    value: int
    inactive: bool
    menu_label: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["ui_minimum"] = max(self.minimum, CONTROL_UI_MINIMUMS.get(self.name, self.minimum))
        payload["ui_maximum"] = min(self.maximum, CONTROL_UI_MAXIMUMS.get(self.name, self.maximum))
        return payload


CONTROL_LINE = re.compile(
    r"^\s*(?P<name>[a-z0-9_]+)\s+0x[0-9a-f]+\s+\((?P<kind>[^)]+)\)\s*:\s*(?P<details>.*)$"
)
CONTROL_VALUE = re.compile(r"\b(?P<key>min|max|step|value)=(-?\d+)")
MENU_LABEL = re.compile(r"\bvalue=-?\d+\s+\((?P<label>[^)]+)\)")

DASHBOARD_CONTROL_NAMES = (
    "auto_exposure",
    "white_balance_automatic",
    "brightness",
    "contrast",
    "saturation",
    "gain",
    "sharpness",
    "white_balance_temperature",
    "exposure_time_absolute",
)
CONTROL_SET_ORDER = DASHBOARD_CONTROL_NAMES
CONTROL_ALLOWED_VALUES = {
    "auto_exposure": {1, 3},
    "white_balance_automatic": {0, 1},
}
CONTROL_UI_MINIMUMS = {
    "exposure_time_absolute": 3,
}
CONTROL_UI_MAXIMUMS = {
    "exposure_time_absolute": 250,
    "gain": 128,
}


PROFILES: dict[str, CameraProfile] = {
    "auto": CameraProfile(
        name="auto",
        label="Auto",
        controls={
            "auto_exposure": 3,
            "white_balance_automatic": 1,
            "brightness": 128,
            "contrast": 128,
            "saturation": 128,
            "gain": 0,
            "backlight_compensation": 0,
            "power_line_frequency": 1,
        },
    ),
    "outdoor-shade": CameraProfile(
        name="outdoor-shade",
        label="Outdoor shade",
        controls={
            "auto_exposure": 1,
            "exposure_time_absolute": 9,
            "white_balance_automatic": 1,
            "brightness": 134,
            "contrast": 145,
            "saturation": 185,
            "gain": 42,
            "backlight_compensation": 1,
            "power_line_frequency": 1,
        },
    ),
    "low-light": CameraProfile(
        name="low-light",
        label="Low light",
        controls={
            "auto_exposure": 3,
            "white_balance_automatic": 1,
            "brightness": 132,
            "contrast": 128,
            "saturation": 128,
            "backlight_compensation": 1,
            "power_line_frequency": 1,
        },
    ),
}


def run_v4l2(device: str, args: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    command = ["v4l2-ctl", "--device", device, *args]
    return subprocess.run(command, text=True, capture_output=True, check=True, timeout=timeout)


def list_controls(device: str) -> str:
    return run_v4l2(device, ["--list-ctrls"]).stdout


def parse_controls(output: str) -> dict[str, CameraControl]:
    controls: dict[str, CameraControl] = {}
    for line in output.splitlines():
        match = CONTROL_LINE.match(line)
        if not match:
            continue
        details = match.group("details")
        values = {item.group("key"): int(item.group(2)) for item in CONTROL_VALUE.finditer(details)}
        if "value" not in values:
            continue
        kind = match.group("kind")
        minimum = values.get("min", 0)
        maximum = values.get("max", 1 if kind == "bool" else values["value"])
        step = max(values.get("step", 1), 1)
        menu = MENU_LABEL.search(details)
        control = CameraControl(
            name=match.group("name"),
            kind=kind,
            minimum=minimum,
            maximum=maximum,
            step=step,
            value=values["value"],
            inactive="flags=inactive" in details,
            menu_label=menu.group("label") if menu else None,
        )
        controls[control.name] = control
    return controls


def read_controls(device: str) -> dict[str, CameraControl]:
    return parse_controls(list_controls(device))


def detect_profile(controls: dict[str, CameraControl]) -> str | None:
    for profile_name, profile in PROFILES.items():
        matches = True
        for name, expected in profile.controls.items():
            control = controls.get(name)
            tolerance = 1 if name == "exposure_time_absolute" else 0
            if control is None or abs(control.value - expected) > tolerance:
                matches = False
                break
        if matches:
            return profile_name
    return None


def camera_state(device: str) -> dict[str, object]:
    controls = read_controls(device)
    return {
        "device": device,
        "active_profile": detect_profile(controls),
        "profiles": [
            {"name": profile.name, "label": profile.label}
            for profile in PROFILES.values()
        ],
        "controls": {
            name: controls[name].to_dict()
            for name in DASHBOARD_CONTROL_NAMES
            if name in controls
        },
    }


def validate_control_values(
    controls: dict[str, CameraControl],
    values: dict[str, int],
) -> dict[str, int]:
    unknown = sorted(set(values) - set(DASHBOARD_CONTROL_NAMES))
    if unknown:
        raise ValueError(f"unsupported camera controls: {', '.join(unknown)}")
    if not values:
        raise ValueError("at least one camera control is required")

    validated: dict[str, int] = {}
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"camera control {name} must be an integer")
        control = controls.get(name)
        if control is None:
            raise ValueError(f"camera control is unavailable: {name}")
        minimum = max(control.minimum, CONTROL_UI_MINIMUMS.get(name, control.minimum))
        maximum = min(control.maximum, CONTROL_UI_MAXIMUMS.get(name, control.maximum))
        if value < minimum or value > maximum:
            raise ValueError(f"camera control {name} must be between {minimum} and {maximum}")
        if (value - control.minimum) % control.step != 0:
            raise ValueError(f"camera control {name} must use step {control.step}")
        allowed = CONTROL_ALLOWED_VALUES.get(name)
        if allowed is not None and value not in allowed:
            choices = ", ".join(str(choice) for choice in sorted(allowed))
            raise ValueError(f"camera control {name} must be one of: {choices}")
        validated[name] = value

    requested_auto_exposure = validated.get("auto_exposure")
    requested_auto_white_balance = validated.get("white_balance_automatic")
    for name in tuple(validated):
        control = controls[name]
        becomes_active = (
            name == "exposure_time_absolute" and requested_auto_exposure == 1
        ) or (
            name == "white_balance_temperature" and requested_auto_white_balance == 0
        )
        if control.inactive and not becomes_active:
            raise ValueError(f"camera control is currently inactive: {name}")

    if requested_auto_exposure == 3:
        validated.pop("exposure_time_absolute", None)
    if requested_auto_white_balance == 1:
        validated.pop("white_balance_temperature", None)
    return validated


def set_controls(device: str, values: dict[str, int]) -> dict[str, object]:
    current = read_controls(device)
    validated = validate_control_values(current, values)
    for name in CONTROL_SET_ORDER:
        if name in validated:
            run_v4l2(device, [f"--set-ctrl={name}={validated[name]}"], timeout=5)
    return camera_state(device)


def apply_profile(device: str, profile_name: str) -> dict[str, int]:
    if profile_name not in PROFILES:
        known = ", ".join(sorted(PROFILES))
        raise ValueError(f"unknown profile {profile_name!r}; choose one of: {known}")
    profile = PROFILES[profile_name]
    for key, value in profile.controls.items():
        run_v4l2(device, [f"--set-ctrl={key}={value}"], timeout=5)
    return profile.controls


def controls_json(device: str, names: list[str]) -> str:
    result = run_v4l2(device, ["--get-ctrl=" + ",".join(names)])
    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return json.dumps(parsed, sort_keys=True)
