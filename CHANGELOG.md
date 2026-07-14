# Changelog

## 0.6.0 - 2026-07-14

- Add timezone-aware Telegram quiet hours with overnight and all-day schedules.
- Add dashboard controls for enabling and editing the alert schedule.
- Continue archiving motion captures while quiet hours suppress notification delivery.
- Persist alert policy changes atomically and fail open when policy evaluation fails.
- Accept legacy `MOTION_*` environment names so standalone notifier deployments can migrate to the maintained monitor.

## 0.5.0 - 2026-07-14

- Add 24-hour, 7-day, and all-time motion-history filters.
- Add paginated access to older retained captures.
- Report in-range and retained event counts plus archive storage usage.
- Add validated event API range, limit, and cursor parameters.
- Keep longer event browsing sessions stable during periodic dashboard refreshes.

## 0.4.0 - 2026-07-14

- Add live systemd state for motion alerts and automatic exposure recovery.
- Add guarded dashboard toggles to pause or resume either service.
- Support custom motion and exposure service names through environment settings.
- Show the installed app version beside the dashboard title.
- Validate service names and restrict dashboard actions to the two configured roles.

## 0.3.0 - 2026-07-14

- Add camera profile controls to the private dashboard.
- Add live sliders for brightness, contrast, saturation, gain, sharpness, exposure, and white balance.
- Add automatic exposure and white-balance toggles with dependent-control handling.
- Add allowlisted, range-validated camera control APIs with same-origin write protection.
- Detect the active camera profile from current V4L2 values, including device rounding tolerance.
- Cap dashboard gain and exposure controls below the C920's extreme white-frame range.

## 0.2.0 - 2026-07-14

- Add a responsive private dashboard with live camera controls and recent motion captures.
- Preserve `/stream` and `/snapshot` through a same-origin dashboard proxy.
- Add JSON status and health endpoints with frame, exposure, power, temperature, uptime, and storage signals.
- Add low-disk-space reporting to the CLI health check.
- Add a dashboard systemd service and update Tailscale Serve setup for private HTTPS access.
- Use the field-tested moderate C920 low-light profile and recovery thresholds.

## 0.1.0 - 2026-06-30

- Initial USB camera stream, Telegram motion alerts, camera profiles, health checks, and exposure watchdog.
