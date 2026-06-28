# Pi Camera Sentinel

Turn a Raspberry Pi and a USB webcam into a private motion camera with Tailscale streaming and Telegram alerts.

This project is intentionally small: no cloud camera account, no public port forwarding, no heavyweight NVR. It uses `ustreamer` for the local MJPEG feed, Tailscale for private remote access, and a lightweight Python motion detector that sends Telegram snapshots.

## What It Does

- Streams a USB webcam from a Raspberry Pi over HTTP.
- Optionally exposes the feed privately through Tailscale Serve.
- Watches snapshots for motion using frame differencing.
- Sends Telegram photo alerts on motion.
- Can attach short video clips if enabled.
- Provides camera profiles for common USB webcam exposure issues.
- Includes health checks for feed availability and Pi undervoltage warnings.

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
git clone https://github.com/YOURNAME/pi-camera-sentinel.git
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

Open the local feed:

```text
http://PI_HOSTNAME.local:8080/
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

Tailscale Serve will proxy the local camera feed to a private tailnet-only URL. Put that URL in `SENTINEL_FEED_URL` so Telegram alerts include a link back to the live feed.

See [docs/tailscale.md](docs/tailscale.md).

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
