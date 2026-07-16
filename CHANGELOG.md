# Changelog

## 1.4.0 - 2026-07-16

- Classify snapshots older than the configured recovery threshold as stale.
- Keep stale frames from reporting the dashboard and health endpoint as online.
- Retry interrupted browser streams with bounded exponential backoff.
- Reconnect immediately after camera or network recovery.
- Refresh the stream when a long-hidden dashboard tab becomes visible again.
- Keep Pause authoritative by suppressing all automatic reconnect attempts.
- Expose explicit viewer states for connecting, live, retrying, offline, and paused sessions.

## 1.3.0 - 2026-07-15

- Add deterministic archive retention limits by file count, age, and total size.
- Apply the same policy to saved photos and optional motion video clips.
- Preserve the newest contiguous set of captures when count or size limits are exceeded.
- Add a JSON cleanup command with a non-destructive `--dry-run` mode.
- Report current, pending, and projected archive usage through the event API.
- Show the active archive policy and cleanup state in the dashboard.
- Keep the existing 200-file limit while leaving new age and size limits disabled by default.

## 1.2.0 - 2026-07-15

- Read Raspberry Pi `vcgencmd get_throttled` hardware flags in addition to kernel logs.
- Distinguish active throttling, recently recovered undervoltage, and historical since-boot events.
- Expose current and historical power flags through the healthcheck and dashboard status API.
- Degrade dashboard health only for active or recent power problems, not sticky historical flags.
- Highlight the Power metric with a concise explanation of the current hardware state.
- Keep the legacy `undervoltage_seen` field for existing integrations.

## 1.1.0 - 2026-07-15

- Add a dashboard action for immediately restarting the configured camera feed service.
- Record feed failures, automatic and manual restarts, failed restarts, and recoveries.
- Keep a bounded 20-entry recovery history and show the five most recent incidents.
- Reload persisted watchdog state each cycle so dashboard actions remain authoritative.
- Preserve v1.0 recovery state files that do not contain incident history.

## 1.0.0 - 2026-07-14

- Add an automatic watchdog for unavailable, offline, empty, or stale camera snapshots.
- Require repeated failed checks and enforce a restart cooldown to prevent loops.
- Persist recovery health, failure counts, restart totals, and timestamps atomically.
- Add one-shot and continuous recovery CLI commands.
- Add a dedicated systemd service and installer support.
- Show feed-recovery health and a pause control in the private dashboard.
- Validate the configured stream service before any systemd restart.

## 0.9.0 - 2026-07-14

- Group nearby motion detections into one Telegram media album.
- Keep the first and latest representative frames while reporting the full burst count.
- Flush pending batches when the camera is unavailable or the service stops.
- Include batch counts, duration, captures, and private event links in Home Assistant payloads.
- Show the active batch window and photo limit in the private dashboard.
- Preserve immediate single-photo delivery when batching is disabled.

## 0.8.0 - 2026-07-14

- Add optional Home Assistant-compatible JSON webhooks for motion events.
- Include camera, host, timestamp, changed ratio, capture name, and private event links.
- Keep webhook failures isolated from Telegram delivery and capture retention.
- Continue webhook delivery during Telegram quiet hours for local automations.
- Add a secret-safe dashboard integration state and test action.
- Add a `send-webhook-test` CLI command without exposing the configured URL.

## 0.7.0 - 2026-07-14

- Add a pointer- and touch-friendly dashboard editor for ignored motion areas.
- Persist up to eight normalized mask regions atomically beside the alert policy.
- Exclude masked pixels from both motion-change counts and the active detection area.
- Reload updated masks in the running detector without restarting the service.
- Preserve the visible stream and archived captures while masks filter detection only.

## 0.6.1 - 2026-07-14

- Keep automatic exposure active in the C920 low-light recovery profile.
- Stop pinning low-light exposure and gain to values that can produce a black frame.
- Add regression coverage for safe low-light recovery controls.

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
