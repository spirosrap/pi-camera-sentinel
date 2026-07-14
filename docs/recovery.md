# Automatic Feed Recovery

Pi Camera Sentinel can recover a stream process that is still running but no longer provides a usable current frame. The watchdog is separate from the exposure watchdog: feed recovery restarts the stream service, while exposure recovery changes camera controls for black or washed-out images.

## Enable The Watchdog

```bash
sudo systemctl enable --now pi-camera-recovery-watchdog.service
```

Check its current state:

```bash
systemctl status pi-camera-recovery-watchdog.service
pi-camera-sentinel recovery-step --json
```

The private dashboard shows whether the service is active, the latest check state, and the cumulative restart count. It also provides a pause toggle, a **Restart feed** action, and the five most recent recovery incidents.

## Conservative Defaults

```text
SENTINEL_STREAM_SERVICE=pi-camera-stream.service
SENTINEL_RECOVERY_SERVICE=pi-camera-recovery-watchdog.service
SENTINEL_RECOVERY_STATE_FILE=/var/lib/pi-camera-sentinel/recovery-state.json
SENTINEL_RECOVERY_INTERVAL_SECONDS=15
SENTINEL_RECOVERY_FAILURE_THRESHOLD=3
SENTINEL_RECOVERY_STALE_SECONDS=20
SENTINEL_RECOVERY_COOLDOWN_SECONDS=120
```

Three consecutive failed checks are required, so one slow request does not restart the camera. After a restart attempt, the two-minute cooldown prevents a disconnected or underpowered camera from creating a rapid restart loop.

## What Counts As Failed

- The snapshot request fails or returns an HTTP error.
- The response is not an image or is empty.
- ustreamer explicitly reports the camera offline.
- The ustreamer frame timestamp is older than the configured stale limit.

The watchdog does not compare image pixels. A completely still scene is valid and cannot be mistaken for a frozen feed. Dark and bright frames are left to the exposure watchdog.

## Custom Stream Services

Installations that use a custom ustreamer unit must set its exact systemd name:

```text
SENTINEL_STREAM_SERVICE=camera-stream.service
```

Service names are validated before systemd is called. Recovery state contains no bot tokens, webhook URLs, or other secrets.

## Manual Recovery And History

Use **Restart feed** in the private dashboard when the stream needs immediate intervention. The same-origin endpoint restarts only the service named by `SENTINEL_STREAM_SERVICE`; arbitrary service names are never accepted from the browser. A manual restart also starts the normal cooldown so it cannot combine with the watchdog into a rapid restart loop.

The state file retains the 20 most recent feed failures, automatic or manual restart attempts, failed restarts, and successful recoveries. The dashboard shows the newest five. Existing v1.0 state files are upgraded in place when the next recovery event is written.
