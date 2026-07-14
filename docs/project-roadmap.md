# Project Roadmap

## MVP

- USB webcam stream through `ustreamer`
- Telegram photo alerts on motion
- Tailscale Serve helper
- health check command
- low-disk-space health check
- private web dashboard and same-origin stream proxy
- dashboard camera profile and manual tuning controls
- dashboard motion-alert and exposure-watchdog state with pause controls
- filterable event history with archive totals and pagination
- timezone-aware Telegram quiet hours with dashboard controls
- masked zones for motion detection with dashboard editor
- optional Home Assistant webhook output
- batched Telegram albums for nearby motion detections
- camera tuning profiles
- exposure watchdog for black/washed-out frames
- systemd installer

## Non-Goals For Now

- public cloud relay
- multi-camera NVR
- face/person detection
- long-term video archive
- phone app

The goal is a small private utility that is easy to audit and recover.
