# Pi Camera Sentinel

Turn a Raspberry Pi and a USB webcam into a private motion camera with Tailscale streaming and Telegram alerts.

This project is intentionally small: no cloud camera account, no public port forwarding, no heavyweight NVR. It uses `ustreamer` for the local MJPEG feed, Tailscale for private remote access, and a lightweight Python motion detector that sends Telegram snapshots.

## What It Does

- Streams a USB webcam from a Raspberry Pi over HTTP.
- Presents a private, responsive dashboard with live status and filterable motion history.
- Summarizes motion activity with range-aware trends and peak periods.
- Drills from activity periods into their exact retained captures.
- Reviews captures continuously with keyboard navigation and automatic archive paging.
- Uses lightweight in-memory gallery thumbnails and lazy dashboard initialization for fast remote access.
- Optionally exposes the feed privately through Tailscale Serve.
- Can move sustained Tailscale streaming to a more capable relay host without re-encoding camera frames.
- Watches snapshots for motion using frame differencing.
- Supports dashboard-drawn ignored areas for excluding noisy motion zones.
- Sends Telegram photo alerts on motion.
- Groups nearby detections into one Telegram album instead of separate alerts.
- Can emit Home Assistant-compatible JSON webhooks for motion automations.
- Supports timezone-aware Telegram quiet hours while continuing to archive motion.
- Bounds the local photo and video archive by count, age, and total size.
- Can attach short video clips if enabled.
- Provides camera profiles for common USB webcam exposure issues.
- Can automatically switch between day and low-light exposure profiles.
- Automatically restarts an unavailable or stale feed after repeated failed checks.
- Automatically reconnects open dashboards after stream, network, or tab-suspension interruptions.
- Records recent feed outages, restart attempts, and successful recoveries.
- Can send deduplicated Telegram updates when automatic feed recovery acts.
- Can send confirmed Telegram warnings and recoveries for Pi power, temperature, and storage.
- Includes health checks for feed availability, live Pi power throttling, and storage.
- Reports low storage, CPU temperature, frame freshness, and camera availability.
- Shows live motion-alert and exposure-watchdog service state with pause and resume controls.

## Hardware

Tested with:

- Raspberry Pi 3B
- Logitech C920 USB webcam
- Debian/Raspberry Pi OS style systemd environment

It should also work with many UVC USB webcams that appear as `/dev/video0` or under `/dev/v4l/by-id/`.

For stability, use a strong 5V Pi power supply and a short power cable. If the webcam causes undervoltage or USB reconnects, use a powered USB hub.

## Quick Start

On the Pi:

```bash
git clone https://github.com/spirosrap/pi-camera-sentinel.git
cd pi-camera-sentinel
sudo scripts/install.sh
```

Edit the config:

```bash
sudoedit /etc/pi-camera-sentinel.env
```

Start the camera feed:

```bash
sudo systemctl enable --now pi-camera-stream.service
pi-camera-sentinel healthcheck
```

Start the dashboard:

```bash
sudo systemctl enable --now pi-camera-dashboard.service
```

Enable automatic exposure recovery:

```bash
sudo systemctl enable --now pi-camera-exposure-watchdog.service
```

Enable automatic feed recovery:

```bash
sudo systemctl enable --now pi-camera-recovery-watchdog.service
```

Enable system health alerts:

```bash
sudo systemctl enable --now pi-camera-health-watchdog.service
```

Open the local dashboard:

```text
http://127.0.0.1:8090/
```

Configure Telegram:

1. Create a bot with Telegram's `@BotFather`.
2. Put the bot token in `/etc/pi-camera-sentinel.env`.
3. Send any message to the new bot.
4. Run:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel show-chat-ids'
```

Put the chat ID in `/etc/pi-camera-sentinel.env`, then send a test:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel send-test'
```

Start motion alerts:

```bash
sudo systemctl enable --now pi-camera-motion.service
```

## Private Remote Viewing With Tailscale

Install and log into Tailscale on the Pi, then run:

```bash
sudo scripts/tailscale-serve-setup.sh
```

Tailscale Serve will proxy the dashboard to a private HTTPS URL. The dashboard keeps the camera-compatible `/stream` and `/snapshot` routes, so existing feed links continue to work. Put the dashboard URL in `SENTINEL_FEED_URL` so Telegram alerts link back to it.

See [docs/tailscale.md](docs/tailscale.md).

For a Pi that becomes thermally limited while serving MJPEG through Tailscale, install the optional relay on a faster always-on computer. The Pi keeps camera capture, motion detection, and the authoritative dashboard; the relay carries camera bytes over the trusted LAN and terminates Tailscale HTTPS. See [docs/relay-host.md](docs/relay-host.md).

## Web Dashboard

The `pi-camera-sentinel serve` command provides a small same-origin web app on port `8090`. It includes:

- live, pause, reconnect, snapshot, and fullscreen controls
- pause-aware automatic stream retries with visible reconnect status
- current frame age, resolution, dropped-frame count, and exposure level
- camera, live Raspberry Pi power flags, temperature, uptime, and storage status
- motion-alert and exposure-recovery state with pause and resume toggles
- feed-recovery state, incident history, manual restart action, and pause control
- active operational Telegram alert state for automatic feed recovery
- system-health alert state with active-condition count and pause control
- active Telegram alert-batching window and photo limit
- secret-safe Home Assistant webhook state and test delivery
- quiet-hours schedule controls for Telegram notifications
- a dedicated `/motion-zones` page with a pointer- and touch-friendly editor for ignored motion areas
- camera profiles plus safe manual exposure, color, gain, sharpness, and white-balance controls
- retained motion snapshots with 24-hour, 7-day, and all-time filters
- motion activity totals, active periods, peak period, and rolling trend chart
- selectable activity periods with exact server-backed event filtering
- responsive capture review with previous/next controls, metadata, and original-file download
- archive totals and paginated access to older captures
- active archive limits and pending cleanup status
- `/healthz`, `/api/status`, `/api/camera`, `/api/policy`, `/api/masks`, `/api/recovery/restart`, and `/api/webhook/test` endpoints for monitoring and control

The event API at `/api/events` accepts a validated `window` (`24h`, `7d`, or `all`), a page `limit`, an optional `before` cursor, and paired `period_start` / `period_end` timestamps for activity drill-down. Responses include retained-file counts, storage totals, archive-retention state, reconciled activity buckets, and selected-period metadata as well as the current page. See [docs/activity-insights.md](docs/activity-insights.md).

Selecting a retained event opens a continuous review viewer with keyboard navigation, automatic page loading, and original-file download. See [docs/archive-review.md](docs/archive-review.md).

The dashboard keeps the live view on the critical path, defers lower sections until they approach the viewport, prewarms its newest 320 x 180 gallery previews, and refreshes slower Pi probes away from interactive requests while retaining original captures unchanged. See [docs/performance.md](docs/performance.md).

The server proxies `/stream` and `/snapshot` to `ustreamer`, which keeps the raw camera port private when Tailscale Serve points at the dashboard.

## Power Diagnostics

On Raspberry Pi hardware, the dashboard and `healthcheck` command read `vcgencmd get_throttled`. They distinguish a power limit that is active now from a recently recovered undervoltage warning and a sticky event that only records something happened since the last boot. Historical flags remain visible without keeping the whole dashboard in a degraded state.

The status API preserves `system.undervoltage_seen` for compatibility and adds structured details under `system.power`, including the raw flag value and individual current and occurred flags. See [docs/power-diagnostics.md](docs/power-diagnostics.md).

Camera writes accept only known V4L2 controls and integer values inside the device-reported range. Browser writes also require a same-origin JSON request. The dashboard deliberately caps manual gain at `128` and exposure at `250` to avoid the extreme settings that can wash a C920 frame completely white.

The dashboard controls the service names in `SENTINEL_MOTION_SERVICE`, `SENTINEL_EXPOSURE_SERVICE`, `SENTINEL_RECOVERY_SERVICE`, and `SENTINEL_HEALTH_SERVICE`. The defaults match the included systemd units; installations with custom unit names can override them in `/etc/pi-camera-sentinel.env`.

## Automatic Feed Recovery

The recovery watchdog checks the snapshot endpoint every 15 seconds. It restarts the configured stream service only after three consecutive failures, then waits at least two minutes before another restart:

```text
SENTINEL_STREAM_SERVICE=pi-camera-stream.service
SENTINEL_RECOVERY_INTERVAL_SECONDS=15
SENTINEL_RECOVERY_FAILURE_THRESHOLD=3
SENTINEL_RECOVERY_STALE_SECONDS=20
SENTINEL_RECOVERY_COOLDOWN_SECONDS=120
```

A failed HTTP request, non-image or empty response, explicit ustreamer offline signal, or frame timestamp older than the stale limit counts as a failure. Identical pixels do not count as stale, so a still scene cannot cause a restart loop. Recovery state, restart totals, and the 20 most recent incidents are stored atomically in `SENTINEL_RECOVERY_STATE_FILE` and displayed in the dashboard. The dashboard also provides a guarded **Restart feed** action for immediate intervention.

Open dashboard tabs recover separately from the Pi watchdog. An interrupted browser stream retries after 1, 2, 4, 8, 16, and then at most 30 seconds. It reconnects immediately when the status API or browser reports recovery, and refreshes after a tab has been hidden for at least 15 seconds. Pausing the live view cancels and suppresses retries until it is resumed.

Enable operational Telegram updates for automatic restart attempts and their eventual recovery with:

```text
SENTINEL_RECOVERY_TELEGRAM_ALERTS=1
```

These alerts use the existing bot and chat configuration. They ignore transient failed checks and manual dashboard restarts, do not replay old history when first enabled, and are not suppressed by motion quiet hours. Telegram delivery failures never block the watchdog and retry on its next cycle.

Run one check manually with `pi-camera-sentinel recovery-step --json`. See [docs/recovery.md](docs/recovery.md).

## System Health Alerts

The health alert watchdog samples active Raspberry Pi power flags, CPU temperature, and archive free space. It waits for three consecutive unhealthy samples before sending a warning and two consecutive healthy samples before sending a recovery:

```text
SENTINEL_HEALTH_INTERVAL_SECONDS=60
SENTINEL_HEALTH_FAILURE_THRESHOLD=3
SENTINEL_HEALTH_RECOVERY_THRESHOLD=2
SENTINEL_HEALTH_TEMPERATURE_MAX_C=80
SENTINEL_HEALTH_TELEGRAM_ALERTS=1
```

The first sample becomes a silent baseline, so enabling the service never reports conditions that were already active. State and pending delivery are persisted atomically. Telegram failures retry without stopping health sampling, and operational health messages are independent of motion quiet hours.

Run one sample manually with `pi-camera-sentinel health-alert-step --json`. See [docs/system-health-alerts.md](docs/system-health-alerts.md).

## Archive Retention

The motion service applies archive limits after every delivered batch. The default preserves the existing behavior of keeping the newest 200 captures; optional age and total-size limits are disabled until configured:

```text
SENTINEL_RETENTION_FILES=200
SENTINEL_RETENTION_DAYS=0
SENTINEL_RETENTION_MB=0
```

Preview the exact candidates before applying a changed policy:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel retention-cleanup --dry-run'
```

Run the same command without `--dry-run` to apply it immediately. See [docs/archive-retention.md](docs/archive-retention.md) for ordering and JSON output details.

Quiet hours are stored atomically in `SENTINEL_POLICY_FILE`. Set `SENTINEL_TIMEZONE` to an IANA timezone such as `Europe/Athens` when the schedule should not follow the Pi's system timezone. Motion captures remain in the archive during quiet hours; only Telegram delivery is suppressed.

Motion masks are stored atomically in `SENTINEL_MASK_FILE`, which defaults to `motion-masks.json` beside the alert policy. The dedicated `/motion-zones` editor supports up to eight normalized rectangles and labels its camera image as a refreshed still frame rather than a live feed. Masked areas remain visible in the feed and saved captures; they are excluded only from motion detection. The running monitor reloads changes within five seconds.

## Home Assistant Webhook

Create a webhook-triggered Home Assistant automation and put its full URL in the private environment file:

```text
SENTINEL_HOME_ASSISTANT_WEBHOOK_URL=http://homeassistant.local:8123/api/webhook/your-secret-id
SENTINEL_WEBHOOK_TIMEOUT=5
```

Restart the motion and dashboard services, then use the dashboard's **Send test** action or run:

```bash
sudo pi-camera-sentinel send-webhook-test
```

Motion events include the camera name, Pi hostname, timestamp, changed-pixel ratio, capture filename, feed URL, and event URL. Webhooks are sent during Telegram quiet hours because the schedule suppresses Telegram delivery only. Delivery failures are logged but do not block Telegram alerts or capture retention. See [docs/home-assistant.md](docs/home-assistant.md).

## Camera Tuning

List camera controls:

```bash
pi-camera-sentinel camera-controls
```

Apply a profile:

```bash
sudo pi-camera-sentinel camera-profile outdoor-shade
```

Available profiles:

- `auto`
- `outdoor-shade`
- `low-light`

See [docs/camera-tuning.md](docs/camera-tuning.md).

Enable automatic day/night recovery:

```bash
sudo systemctl enable --now pi-camera-exposure-watchdog.service
```

## Motion Tuning

The default motion settings are deliberately conservative:

```text
SENTINEL_CHANGED_RATIO=0.035
SENTINEL_MIN_FRAMES=2
SENTINEL_COOLDOWN_SECONDS=60
SENTINEL_ALERT_BATCH_SECONDS=8
SENTINEL_ALERT_BATCH_MAX_PHOTOS=4
```

Sample the current scene:

```bash
pi-camera-sentinel sample 10
```

If the scene is noisy, increase `SENTINEL_CHANGED_RATIO`. If small motion is missed, lower it.

Nearby detections are collected for eight seconds and delivered as one Telegram album containing up to four representative frames. The first frame is retained and the newest frame continually replaces the final slot after the limit is reached. Set `SENTINEL_ALERT_BATCH_SECONDS=0` for immediate single-photo alerts. The normal cooldown starts when a batch is delivered.

Use **Motion zones** in the dashboard to exclude areas such as moving plants, reflections, clocks, or status lights. Add and apply rectangles over a current snapshot; no service restart is required.

## Security Notes

- Do not commit `/etc/pi-camera-sentinel.env`.
- Do not expose the camera port publicly.
- Prefer Tailscale, VPN, or LAN-only access.
- Telegram bot tokens control your bot; treat them like passwords.
- Home Assistant webhook URLs contain secret IDs; do not commit or expose them.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python3 -m pytest
```

The project does not need camera hardware for its unit tests.
