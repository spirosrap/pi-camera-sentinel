# Pi Camera Sentinel

Turn a Raspberry Pi and a USB webcam into a private motion camera with Tailscale streaming and Telegram alerts.

This project is intentionally small: no cloud camera account, no public port forwarding, no heavyweight NVR. It uses `ustreamer` for the local MJPEG feed, Tailscale for private remote access, and a lightweight Python motion detector that sends Telegram snapshots.

## What It Does

- Streams a USB webcam from a Raspberry Pi over HTTP.
- Presents a private, responsive dashboard with live status and recent motion captures.
- Optionally exposes the feed privately through Tailscale Serve.
- Watches snapshots for motion using frame differencing.
- Sends Telegram photo alerts on motion.
- Can attach short video clips if enabled.
- Provides camera profiles for common USB webcam exposure issues.
- Can automatically switch between day and low-light exposure profiles.
- Includes health checks for feed availability and Pi undervoltage warnings.
- Reports low storage, CPU temperature, frame freshness, and camera availability.

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

## Web Dashboard

The `pi-camera-sentinel serve` command provides a small same-origin web app on port `8090`. It includes:

- live, pause, reconnect, snapshot, and fullscreen controls
- current frame age, resolution, dropped-frame count, and exposure level
- camera, power, temperature, uptime, and storage status
- camera profiles plus safe manual exposure, color, gain, sharpness, and white-balance controls
- the most recent retained motion snapshots
- `/healthz`, `/api/status`, and `/api/camera` endpoints for monitoring and control

The server proxies `/stream` and `/snapshot` to `ustreamer`, which keeps the raw camera port private when Tailscale Serve points at the dashboard.

Camera writes accept only known V4L2 controls and integer values inside the device-reported range. Browser writes also require a same-origin JSON request. The dashboard deliberately caps manual gain at `128` and exposure at `250` to avoid the extreme settings that can wash a C920 frame completely white.

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
```

Sample the current scene:

```bash
pi-camera-sentinel sample 10
```

If the scene is noisy, increase `SENTINEL_CHANGED_RATIO`. If small motion is missed, lower it.

## Security Notes

- Do not commit `/etc/pi-camera-sentinel.env`.
- Do not expose the camera port publicly.
- Prefer Tailscale, VPN, or LAN-only access.
- Telegram bot tokens control your bot; treat them like passwords.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python3 -m pytest
```

The project does not need camera hardware for its unit tests.
