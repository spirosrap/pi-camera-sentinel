from pi_camera_sentinel.config import Settings


def test_legacy_motion_environment_aliases(monkeypatch, tmp_path):
    monkeypatch.delenv("SENTINEL_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("SENTINEL_CHANGED_RATIO", raising=False)
    monkeypatch.delenv("SENTINEL_MASK_FILE", raising=False)
    monkeypatch.delenv("MOTION_MASK_FILE", raising=False)
    monkeypatch.setenv("MOTION_OUTPUT_DIR", str(tmp_path / "legacy"))
    monkeypatch.setenv("MOTION_CHANGED_RATIO", "0.125")
    monkeypatch.setenv("MOTION_POLICY_FILE", str(tmp_path / "policy.json"))
    monkeypatch.setenv("MOTION_TIMEZONE", "Europe/Athens")

    settings = Settings.from_env()

    assert settings.output_dir == tmp_path / "legacy"
    assert settings.changed_ratio == 0.125
    assert settings.policy_file == tmp_path / "policy.json"
    assert settings.mask_file == tmp_path / "motion-masks.json"
    assert settings.timezone == "Europe/Athens"


def test_sentinel_environment_takes_precedence(monkeypatch):
    monkeypatch.setenv("SENTINEL_POLL_SECONDS", "2.5")
    monkeypatch.setenv("MOTION_POLL_SECONDS", "9.5")

    assert Settings.from_env().poll_seconds == 2.5


def test_home_assistant_webhook_configuration(monkeypatch):
    monkeypatch.setenv("SENTINEL_HOME_ASSISTANT_WEBHOOK_URL", "https://ha.example/api/webhook/id")
    monkeypatch.setenv("SENTINEL_WEBHOOK_URL", "https://fallback.example/hook")
    monkeypatch.setenv("SENTINEL_WEBHOOK_TIMEOUT", "2.5")

    settings = Settings.from_env()

    assert settings.webhook_url == "https://ha.example/api/webhook/id"
    assert settings.webhook_timeout == 2.5
