# Changelog

## 0.2.0 - 2026-07-14

- Add a responsive private dashboard with live camera controls and recent motion captures.
- Preserve `/stream` and `/snapshot` through a same-origin dashboard proxy.
- Add JSON status and health endpoints with frame, exposure, power, temperature, uptime, and storage signals.
- Add low-disk-space reporting to the CLI health check.
- Add a dashboard systemd service and update Tailscale Serve setup for private HTTPS access.
- Use the field-tested moderate C920 low-light profile and recovery thresholds.

## 0.1.0 - 2026-06-30

- Initial USB camera stream, Telegram motion alerts, camera profiles, health checks, and exposure watchdog.
