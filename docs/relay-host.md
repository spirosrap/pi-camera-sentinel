# Relay Host

A Raspberry Pi can capture a hardware MJPEG stream efficiently but still spend a full CPU core encrypting a sustained Tailscale connection. A relay host moves HTTPS, Tailscale, and remote-client work to a faster machine without recompressing the camera image.

## Data Path

```text
USB camera -> Raspberry Pi ustreamer -> trusted LAN -> relay host -> Tailscale HTTPS -> viewer
```

The relay sends `/stream` and `/snapshot` straight to the Pi over the LAN. Dashboard pages, controls, health, motion history, and retained events continue to come from the Pi dashboard, so displayed system state still describes the Pi.

The relay fans all `/stream` viewers out from one lazy upstream MJPEG connection to the Pi. It releases that connection shortly after the last viewer disconnects, so background tabs and multiple devices cannot multiply Pi stream work.

If the Pi stream stalls, the relay reconnects that one upstream connection while keeping browser viewers attached. `SENTINEL_RELAY_STREAM_READ_TIMEOUT` controls how quickly a stalled upstream is replaced; `SENTINEL_RELAY_STREAM_CLIENT_TIMEOUT` controls how long an attached viewer waits through recovery. The defaults are 10 and 90 seconds respectively.

The relay preserves the original JPEG frame bytes. It does not resize or re-encode them, so resolution, quality, and frame rate remain controlled by `ustreamer` on the Pi.

## Install

On an always-on Debian or Ubuntu relay host:

```bash
git clone https://github.com/spirosrap/pi-camera-sentinel.git
cd pi-camera-sentinel
sudo scripts/install-relay.sh
sudoedit /etc/pi-camera-relay.env
```

Configure the media URLs with the Pi's trusted LAN hostname:

```text
SENTINEL_RELAY_STREAM_URL=http://pi-camera.local:8080/stream
SENTINEL_RELAY_SNAPSHOT_URL=http://pi-camera.local:8080/snapshot
```

Keep the Pi dashboard bound to loopback. One option is a restricted SSH local forward from the relay host:

```bash
ssh -NT \
  -L 127.0.0.1:18090:127.0.0.1:8090 \
  pi@pi-camera.local
```

Then use the forwarded dashboard in the relay config:

```text
SENTINEL_RELAY_DASHBOARD_URL=http://127.0.0.1:18090
```

Start the relay and publish only its loopback listener to the tailnet:

```bash
sudo systemctl enable --now pi-camera-relay.service
sudo tailscale serve --bg --yes 8091
tailscale serve status
```

Set `SENTINEL_FEED_URL` on the Pi to the relay host's new HTTPS URL so Telegram and webhook links use the cooler path.

To preserve old bookmarks and previously sent Telegram links, the retired Pi URL can serve a lightweight redirect instead of the stream. Install `systemd/pi-camera-redirect.service`, set `SENTINEL_REDIRECT_TARGET_URL` in `/etc/pi-camera-redirect.env`, and point the Pi's old Tailscale Serve configuration at port `8092`. The old node then handles only the initial redirect; all sustained camera traffic goes to the relay host.

## Verification

Check the same-origin dashboard and direct media paths:

```bash
curl -fsS https://relay-host.your-tailnet.ts.net/api/status
curl -fsS -o /dev/null https://relay-host.your-tailnet.ts.net/snapshot
curl -fsS --max-time 10 -o /dev/null https://relay-host.your-tailnet.ts.net/stream
```

While the stream is open, compare `vcgencmd measure_temp`, `vcgencmd measure_clock arm`, and `vcgencmd get_throttled` on the Pi. The relay removes sustained Tailscale encryption from the Pi, but it cannot repair active undervoltage or replace cooling when the board is already hot from another workload.
