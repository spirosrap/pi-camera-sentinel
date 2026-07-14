import subprocess

import pytest

from pi_camera_sentinel.services import restart_service, service_state, set_service_active, valid_service_name


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.commands = []

    def __call__(self, command, **_kwargs):
        self.commands.append(command)
        return self.responses.pop(0)


def completed(stdout: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def test_service_state_reports_active_unit():
    runner = FakeRunner(
        [
            completed(
                "\n".join(
                    [
                        "LoadState=loaded",
                        "ActiveState=active",
                        "SubState=running",
                        "UnitFileState=enabled",
                        "ActiveEnterTimestamp=Tue 2026-07-14 16:40:09 BST",
                        "InactiveEnterTimestamp=",
                    ]
                )
            )
        ]
    )

    result = service_state("pi-camera-motion.service", runner=runner)

    assert result["available"] is True
    assert result["active"] is True
    assert result["state"] == "active"
    assert result["sub_state"] == "running"
    assert result["changed_at"] == "Tue 2026-07-14 16:40:09 BST"
    assert runner.commands[0][:3] == ["systemctl", "show", "pi-camera-motion.service"]


def test_service_state_reports_missing_unit_without_raising():
    runner = FakeRunner([completed("LoadState=not-found\nActiveState=inactive")])

    result = service_state("missing.service", runner=runner)

    assert result["available"] is False
    assert result["state"] == "unavailable"
    assert result["error"] == "systemd service is not installed"


def test_set_service_active_uses_only_start_or_stop():
    runner = FakeRunner(
        [
            completed(),
            completed("LoadState=loaded\nActiveState=inactive\nSubState=dead\nUnitFileState=enabled"),
        ]
    )

    result = set_service_active("watchdog.service", False, runner=runner)

    assert runner.commands[0] == ["systemctl", "stop", "watchdog.service"]
    assert result["active"] is False
    assert result["state"] == "paused"


def test_restart_service_uses_validated_systemctl_restart():
    runner = FakeRunner([completed()])

    restart_service("camera-stream.service", runner=runner)

    assert runner.commands == [["systemctl", "restart", "camera-stream.service"]]


def test_service_names_reject_shell_syntax():
    assert valid_service_name("pi-camera-motion.service") is True
    assert valid_service_name("camera@front.service") is True
    assert valid_service_name("camera.service;reboot") is False
    with pytest.raises(ValueError, match="invalid systemd service name"):
        set_service_active("camera.service;reboot", True)
    with pytest.raises(ValueError, match="invalid systemd service name"):
        restart_service("camera.service;reboot")
