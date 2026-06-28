# Tailscale Setup

Tailscale gives the camera a private URL reachable only by devices in your tailnet. This avoids router port forwarding and keeps the feed off the public internet.

## Install Tailscale

On Raspberry Pi OS or Debian:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=pi-camera
```

Then authenticate in the browser.

## Serve The Camera

The stream service listens locally on port `8080`. To expose it privately inside the tailnet:

```bash
sudo scripts/tailscale-serve-setup.sh
```

Equivalent manual command:

```bash
sudo tailscale serve reset
sudo tailscale serve --bg --http=80 8080
```

Check status:

```bash
tailscale serve status
```

Use the MagicDNS URL in `SENTINEL_FEED_URL`, for example:

```text
SENTINEL_FEED_URL=http://pi-camera.your-tailnet.ts.net/
```

## Troubleshooting

Check the raw local feed from the Pi:

```bash
curl -fsS http://127.0.0.1:8080/state
```

Check from another tailnet device:

```bash
curl -fsS http://pi-camera.your-tailnet.ts.net/state
```

If MagicDNS is unreliable, use the Tailscale IP directly:

```text
http://100.x.y.z:8080/
```
