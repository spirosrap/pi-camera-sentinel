from pi_camera_sentinel.config import Settings


def test_legacy_motion_environment_aliases(monkeypatch, tmp_path):
    monkeypatch.delenv("SENTINEL_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("SENTINEL_CHANGED_RATIO", raising=False)
    monkeypatch.setenv("MOTION_OUTPUT_DIR", str(tmp_path / "legacy"))
    monkeypatch.setenv("MOTION_CHANGED_RATIO", "0.125")
    monkeypatch.setenv("MOTION_POLICY_FILE", str(tmp_path / "policy.json"))
    monkeypatch.setenv("MOTION_TIMEZONE", "Europe/Athens")

    settings = Settings.from_env()

    assert settings.output_dir == tmp_path / "legacy"
    assert settings.changed_ratio == 0.125
    assert settings.policy_file == tmp_path / "policy.json"
    assert settings.timezone == "Europe/Athens"


def test_sentinel_environment_takes_precedence(monkeypatch):
    monkeypatch.setenv("SENTINEL_POLL_SECONDS", "2.5")
    monkeypatch.setenv("MOTION_POLL_SECONDS", "9.5")

    assert Settings.from_env().poll_seconds == 2.5
