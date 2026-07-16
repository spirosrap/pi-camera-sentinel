# System Health Alerts

Pi Camera Sentinel can monitor Raspberry Pi power, CPU temperature, and motion-archive storage independently of the live camera feed. The watchdog sends one Telegram warning when a condition is confirmed and one recovery when it clears.

## Enable The Watchdog

Configure `/etc/pi-camera-sentinel.env`:

```text
SENTINEL_HEALTH_STATE_FILE=/var/lib/pi-camera-sentinel/health-alert-state.json
SENTINEL_HEALTH_INTERVAL_SECONDS=60
SENTINEL_HEALTH_FAILURE_THRESHOLD=3
SENTINEL_HEALTH_RECOVERY_THRESHOLD=2
SENTINEL_HEALTH_TEMPERATURE_MAX_C=80
SENTINEL_HEALTH_TELEGRAM_ALERTS=1
```

Then start the service:

```bash
sudo systemctl enable --now pi-camera-health-watchdog.service
```

The Telegram bot token and chat ID use the same configuration as motion and feed-recovery alerts.

## Conditions

- **Power** reports only currently active `vcgencmd get_throttled` limits. Sticky since-boot flags do not trigger an alert.
- **Temperature** reports a CPU temperature at or above `SENTINEL_HEALTH_TEMPERATURE_MAX_C`. Unavailable telemetry is not treated as overheating.
- **Storage** reuses `SENTINEL_DISK_MIN_FREE_MB` against the filesystem containing `SENTINEL_OUTPUT_DIR`.

The default three unhealthy samples prevent a short power or temperature fluctuation from producing a warning. The default two healthy samples prevent a momentary recovery from producing a clear message.

## Startup And Delivery

The first observation is a silent baseline. Conditions that already exist when v1.6 starts are tracked but do not generate a migration warning or a later recovery message. A condition must clear and then recur before it can notify.

Per-condition counters and pending Telegram messages are stored atomically in `SENTINEL_HEALTH_STATE_FILE`. State is saved before delivery. A Telegram failure leaves the message queued while later samples continue updating health state; delivery retries on the next cycle. Alerts disabled by configuration are discarded rather than retained as a future backlog.

Health messages are operational and are not suppressed by motion quiet hours.

## One-Shot Check

Run one state transition without starting the service:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel health-alert-step --json'
```

The output includes current per-condition counters and pending delivery. Use `pi-camera-sentinel healthcheck` for the broader immediate snapshot, camera, power, and storage diagnostic.
