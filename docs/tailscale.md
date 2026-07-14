# Tailscale Setup

Tailscale gives the camera a private URL reachable only by devices in your tailnet. This avoids router port forwarding and keeps the feed off the public internet.

## Install Tailscale

On Raspberry Pi OS or Debian:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=pi-camera
```

Then authenticate in the browser.

## Serve The Dashboard

The stream service listens locally on port `8080`, and the dashboard listens on loopback port `8090`. To expose the dashboard privately inside the tailnet:

```bash
sudo scripts/tailscale-serve-setup.sh
```

Equivalent manual command:

```bash
sudo tailscale serve reset
sudo tailscale serve --bg --yes 8090
```

Check status:

```bash
tailscale serve status
```

Use the MagicDNS URL in `SENTINEL_FEED_URL`, for example:

```text
SENTINEL_FEED_URL=https://pi-camera.your-tailnet.ts.net/
```

The dashboard proxies the existing camera paths:

```text
https://pi-camera.your-tailnet.ts.net/stream
https://pi-camera.your-tailnet.ts.net/snapshot
```

## Troubleshooting

Check the raw local feed from the Pi:

```bash
curl -fsS http://127.0.0.1:8080/state
```

Check the dashboard health from the Pi:

```bash
curl -fsS http://127.0.0.1:8090/healthz
```

Check from another tailnet device:

```bash
curl -fsS https://pi-camera.your-tailnet.ts.net/healthz
```

If MagicDNS is unreliable, test the raw camera port from the Pi or another trusted LAN device. Tailscale Serve HTTPS relies on the MagicDNS name for its certificate.
