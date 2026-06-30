# Project Roadmap

## MVP

- USB webcam stream through `ustreamer`
- Telegram photo alerts on motion
- Tailscale Serve helper
- health check command
- camera tuning profiles
- exposure watchdog for black/washed-out frames
- systemd installer

## Good Next Features

- optional Home Assistant webhook output
- masked zones for motion detection
- quiet hours
- alert batching
- low-disk-space health check
- simple web status page

## Non-Goals For Now

- public cloud relay
- multi-camera NVR
- face/person detection
- long-term video archive
- phone app

The goal is a small private utility that is easy to audit and recover.
