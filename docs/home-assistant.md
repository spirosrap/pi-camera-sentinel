# Home Assistant Webhook

Pi Camera Sentinel can post one JSON event to a Home Assistant webhook whenever a motion capture is archived.

## Setup

1. Create a webhook-triggered automation in Home Assistant.
2. Keep the webhook ID private and restrict the automation to the local network when appropriate.
3. Put the full webhook URL in `/etc/pi-camera-sentinel.env`:

```text
SENTINEL_HOME_ASSISTANT_WEBHOOK_URL=http://homeassistant.local:8123/api/webhook/your-secret-id
SENTINEL_WEBHOOK_TIMEOUT=5
```

4. Restart the motion monitor and dashboard.
5. Send a test from the dashboard or CLI:

```bash
sudo pi-camera-sentinel send-webhook-test
```

The dashboard reports only whether the integration is configured and the HTTP result of a test. It never returns the webhook URL.

## Motion Payload

```json
{
  "event": "motion",
  "source": "pi-camera-sentinel",
  "camera": "Pi Camera Sentinel",
  "hostname": "spiros-pi3b",
  "captured_at": "2026-07-14T22:00:00+03:00",
  "changed_ratio": 0.0825,
  "capture": "motion-20260714-220000.jpg",
  "event_url": "https://camera.example/events/motion-20260714-220000.jpg",
  "feed_url": "https://camera.example/"
}
```

`event_url` is included when `SENTINEL_FEED_URL` is an HTTP or HTTPS dashboard URL. The Home Assistant host must be able to reach that private URL to fetch the capture.

Webhook delivery has no automatic retry, avoiding duplicate automations. Failures are logged and do not block Telegram delivery or local capture retention. Telegram quiet hours do not suppress Home Assistant events.
