from __future__ import annotations

import re
import subprocess
from typing import Callable, Iterable


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


def _parse_properties(output: str) -> dict[str, str]:
    return {
        key: value
        for line in output.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }


def _service_payload(name: str, properties: dict[str, str]) -> dict[str, object]:
    load_state = properties.get("LoadState", "unknown")
    if load_state in {"not-found", "unknown"}:
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

    properties = _parse_properties(result.stdout)
    load_state = properties.get("LoadState", "unknown")
    if result.returncode != 0 or load_state in {"not-found", "unknown"}:
        return unavailable_service(name, "systemd service is not installed")

    return _service_payload(name, properties)


def service_states(
    names: Iterable[str],
    *,
    runner: Runner = subprocess.run,
) -> dict[str, dict[str, object]]:
    ordered_names = tuple(dict.fromkeys(names))
    states = {
        name: unavailable_service(name, "invalid systemd service name")
        for name in ordered_names
        if not valid_service_name(name)
    }
    valid_names = [name for name in ordered_names if valid_service_name(name)]
    if not valid_names:
        return states

    command = ["systemctl", "show", *valid_names, "--no-pager", "--property=Id"]
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
        states.update(
            {
                name: unavailable_service(name, "systemd status is unavailable")
                for name in valid_names
            }
        )
        return states

    parsed: dict[str, dict[str, str]] = {}
    blocks = [block for block in result.stdout.strip().split("\n\n") if block.strip()]
    for block in blocks:
        properties = _parse_properties(block)
        unit_id = properties.get("Id")
        if unit_id:
            parsed[unit_id] = properties
    if len(valid_names) == 1 and len(blocks) == 1 and valid_names[0] not in parsed:
        parsed[valid_names[0]] = _parse_properties(blocks[0])

    for name in valid_names:
        properties = parsed.get(name)
        states[name] = (
            _service_payload(name, properties)
            if properties is not None
            else unavailable_service(name, "systemd status is unavailable")
        )
    return states


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


def restart_service(name: str, *, runner: Runner = subprocess.run) -> None:
    if not valid_service_name(name):
        raise ValueError("invalid systemd service name")
    try:
        result = runner(
            ["systemctl", "restart", name],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OSError("systemd service restart is unavailable") from exc
    if result.returncode != 0:
        raise OSError("could not restart systemd service")
