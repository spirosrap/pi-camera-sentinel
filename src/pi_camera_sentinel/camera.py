from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraProfile:
    name: str
    controls: dict[str, int]


PROFILES: dict[str, CameraProfile] = {
    "auto": CameraProfile(
        name="auto",
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
        controls={
            "auto_exposure": 1,
            "exposure_time_absolute": 19,
            "white_balance_automatic": 1,
            "brightness": 132,
            "contrast": 136,
            "saturation": 150,
            "gain": 60,
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
