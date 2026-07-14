# Project Roadmap

## MVP

- USB webcam stream through `ustreamer`
- Telegram photo alerts on motion
- Tailscale Serve helper
- health check command
- low-disk-space health check
- private web dashboard and same-origin stream proxy
- dashboard camera profile and manual tuning controls
- camera tuning profiles
- exposure watchdog for black/washed-out frames
- systemd installer

## Good Next Features

- optional Home Assistant webhook output
- masked zones for motion detection
- quiet hours
- alert batching
- event metadata and alert history
- dashboard watchdog state and pause controls

## Non-Goals For Now

- public cloud relay
- multi-camera NVR
- face/person detection
- long-term video archive
- phone app

The goal is a small private utility that is easy to audit and recover.
