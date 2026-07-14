from __future__ import annotations

import re
import subprocess
from typing import Callable


SERVICE_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.@-]+\.service")
SYSTEMCTL_PROPERTIES = (
    "LoadState",
    "ActiveState",
    "SubState",
    "UnitFileState",
    "ActiveEnterTimestamp",
    "InactiveEnterTimestamp",
)
Runner = Callable[..., subprocess.CompletedProcess[str]]


def valid_service_name(name: str) -> bool:
    return bool(SERVICE_NAME_PATTERN.fullmatch(name))


def unavailable_service(name: str, error: str) -> dict[str, object]:
    return {
        "name": name,
        "available": False,
        "active": False,
        "state": "unavailable",
        "active_state": "unknown",
        "sub_state": "unknown",
        "unit_file_state": "unknown",
        "changed_at": None,
        "error": error,
    }


def service_state(name: str, *, runner: Runner = subprocess.run) -> dict[str, object]:
    if not valid_service_name(name):
        return unavailable_service(name, "invalid systemd service name")

    command = ["systemctl", "show", name, "--no-pager"]
    command.extend(f"--property={property_name}" for property_name in SYSTEMCTL_PROPERTIES)
    try:
        result = runner(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return unavailable_service(name, "systemd status is unavailable")

    properties = {
        key: value
        for line in result.stdout.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }
    load_state = properties.get("LoadState", "unknown")
    if result.returncode != 0 or load_state in {"not-found", "unknown"}:
        return unavailable_service(name, "systemd service is not installed")

    active_state = properties.get("ActiveState", "unknown")
    active = active_state == "active"
    if active:
        state = "active"
        changed_at = properties.get("ActiveEnterTimestamp") or None
    elif active_state == "failed":
        state = "failed"
        changed_at = properties.get("InactiveEnterTimestamp") or None
    else:
        state = "paused"
        changed_at = properties.get("InactiveEnterTimestamp") or None

    return {
        "name": name,
        "available": True,
        "active": active,
        "state": state,
        "active_state": active_state,
        "sub_state": properties.get("SubState", "unknown"),
        "unit_file_state": properties.get("UnitFileState", "unknown"),
        "changed_at": changed_at,
        "error": None,
    }


def set_service_active(
    name: str,
    active: bool,
    *,
    runner: Runner = subprocess.run,
) -> dict[str, object]:
    if not valid_service_name(name):
        raise ValueError("invalid systemd service name")

    action = "start" if active else "stop"
    try:
        result = runner(
            ["systemctl", action, name],
            text=True,
            capture_output=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OSError("systemd service control is unavailable") from exc
    if result.returncode != 0:
        raise OSError(f"could not {action} systemd service")
    return service_state(name, runner=runner)
