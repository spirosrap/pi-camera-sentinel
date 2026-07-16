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


def test_alert_batch_configuration(monkeypatch):
    monkeypatch.setenv("SENTINEL_ALERT_BATCH_SECONDS", "12.5")
    monkeypatch.setenv("SENTINEL_ALERT_BATCH_MAX_PHOTOS", "6")

    settings = Settings.from_env()

    assert settings.alert_batch_seconds == 12.5
    assert settings.alert_batch_max_photos == 6


def test_archive_retention_configuration(monkeypatch):
    monkeypatch.setenv("SENTINEL_RETENTION_FILES", "300")
    monkeypatch.setenv("SENTINEL_RETENTION_DAYS", "14.5")
    monkeypatch.setenv("SENTINEL_RETENTION_MB", "2048")

    settings = Settings.from_env()

    assert settings.retention_files == 300
    assert settings.retention_days == 14.5
    assert settings.retention_mb == 2048


def test_feed_recovery_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_STREAM_SERVICE", "custom-stream.service")
    monkeypatch.setenv("SENTINEL_RECOVERY_SERVICE", "custom-recovery.service")
    monkeypatch.setenv("SENTINEL_RECOVERY_STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setenv("SENTINEL_RECOVERY_INTERVAL_SECONDS", "12.5")
    monkeypatch.setenv("SENTINEL_RECOVERY_FAILURE_THRESHOLD", "4")
    monkeypatch.setenv("SENTINEL_RECOVERY_STALE_SECONDS", "30")
    monkeypatch.setenv("SENTINEL_RECOVERY_COOLDOWN_SECONDS", "180")
    monkeypatch.setenv("SENTINEL_RECOVERY_TELEGRAM_ALERTS", "1")

    settings = Settings.from_env()

    assert settings.stream_service == "custom-stream.service"
    assert settings.recovery_service == "custom-recovery.service"
    assert settings.recovery_state_file == tmp_path / "state.json"
    assert settings.recovery_interval_seconds == 12.5
    assert settings.recovery_failure_threshold == 4
    assert settings.recovery_stale_seconds == 30
    assert settings.recovery_cooldown_seconds == 180
    assert settings.recovery_telegram_alerts is True
