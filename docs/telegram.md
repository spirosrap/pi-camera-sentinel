# Telegram Alerts

Pi Camera Sentinel sends Telegram alerts through a bot. The bot token and chat ID live only in `/etc/pi-camera-sentinel.env`.

## Create A Bot

1. Open Telegram and message `@BotFather`.
2. Run `/newbot`.
3. Copy the token into:

```text
TELEGRAM_BOT_TOKEN=...
```

4. Send any message to your new bot.
5. On the Pi, run:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel show-chat-ids'
```

6. Copy the private chat ID into:

```text
TELEGRAM_CHAT_ID=...
```

## Test Delivery

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel send-test'
```

If this works, start the motion service:

```bash
sudo systemctl enable --now pi-camera-motion.service
```

## Batch Nearby Motion

By default, nearby detections are collected for eight seconds and sent as one Telegram album with up to four representative frames:

```text
SENTINEL_ALERT_BATCH_SECONDS=8
SENTINEL_ALERT_BATCH_MAX_PHOTOS=4
```

The caption reports the full detection count, batch duration, and peak changed-pixel ratio even when the photo limit is reached. The first frame is kept and the newest frame continually replaces the final slot, so the album shows how the scene developed. Set the batch window to `0` to restore immediate single-photo alerts.

## Avoid Spam

Use cooldowns and consecutive-frame checks:

```text
SENTINEL_MIN_FRAMES=2
SENTINEL_COOLDOWN_SECONDS=30
```

The cooldown begins when a completed batch is delivered.

For busy scenes, increase:

```text
SENTINEL_CHANGED_RATIO=0.015
```

The default `0.008` ratio, two samples per second, and 320 x 180 analysis frame are intended to retain small pets farther from the camera. Keep the two-frame confirmation enabled unless one-frame movement is more important than avoiding brief lighting or foliage alerts.

## Quiet Hours

The private dashboard can enable a daily quiet-hours schedule. Motion detected during that window is still saved to the local event archive, but Telegram photos, messages, and clips are suppressed.

## Feed Recovery Updates

Set `SENTINEL_RECOVERY_TELEGRAM_ALERTS=1` to receive text updates when automatic feed recovery restarts the stream, cannot restart it, or confirms that it recovered. These operational messages are independent of motion quiet hours. Transient failed checks and manual restart actions do not send messages.

Recovery delivery is deduplicated through the persisted recovery state. Existing incidents are not replayed when the option is first enabled, and a Telegram failure is retried without interrupting the camera watchdog.

## System Health Updates

Set `SENTINEL_HEALTH_TELEGRAM_ALERTS=1` and enable `pi-camera-health-watchdog.service` to receive confirmed warnings and recoveries for active Pi power limits, high CPU temperature, and low archive storage. The watchdog requires repeated observations, silently baselines conditions present at first startup, and persists pending delivery across restarts.

Health and feed-recovery messages are operational and are not suppressed by motion quiet hours.

Set the schedule timezone in `/etc/pi-camera-sentinel.env`:

```text
SENTINEL_TIMEZONE=Europe/Athens
SENTINEL_POLICY_FILE=/var/lib/pi-camera-sentinel/alert-policy.json
```

Schedules can cross midnight, such as `22:00` until `07:00`. Matching start and end times mean quiet mode lasts all day. If the policy file cannot be read or validated, notification delivery remains enabled.
