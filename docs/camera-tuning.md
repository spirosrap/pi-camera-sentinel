# Camera Tuning

Most UVC webcams expose controls through `v4l2-ctl`. Pi Camera Sentinel includes a few starter profiles, but camera behavior varies by model and lighting.

## Inspect Controls

```bash
pi-camera-sentinel camera-controls
pi-camera-sentinel camera-get
```

## Profiles

`auto` restores simple automatic behavior:

```bash
sudo pi-camera-sentinel camera-profile auto
```

`outdoor-shade` is useful when a bright object or sky causes auto exposure to make shaded areas too dark:

```bash
sudo pi-camera-sentinel camera-profile outdoor-shade
```

`low-light` increases exposure and gain:

```bash
sudo pi-camera-sentinel camera-profile low-light
```

## Making A Profile Persistent

The current MVP applies camera profiles manually. To persist a profile on boot, add an `ExecStartPre` line to `pi-camera-stream.service`, for example:

```ini
ExecStartPre=/usr/local/bin/pi-camera-sentinel camera-profile outdoor-shade
```

Camera controls can block briefly while the device is streaming, so applying a profile before starting `ustreamer` is more reliable.

## Exposure Watchdog

The exposure watchdog samples the current snapshot and applies a profile only when the image is clearly unusable:

- mostly black: apply `SENTINEL_EXPOSURE_NIGHT_PROFILE`
- mostly white: apply `SENTINEL_EXPOSURE_DAY_PROFILE`
- normal frame: hold the current settings

Enable it:

```bash
sudo systemctl enable --now pi-camera-exposure-watchdog.service
```

Run one cycle manually:

```bash
sudo sh -c 'set -a; . /etc/pi-camera-sentinel.env; set +a; pi-camera-sentinel exposure-step --json'
```

Useful config:

```text
SENTINEL_EXPOSURE_WATCHDOG_INTERVAL=60
SENTINEL_EXPOSURE_DAY_PROFILE=auto
SENTINEL_EXPOSURE_NIGHT_PROFILE=low-light
SENTINEL_EXPOSURE_DARK_MEAN_MAX=15
SENTINEL_EXPOSURE_BRIGHT_MEAN_MIN=230
```

This is more reliable than switching by clock time because it responds to the actual image: clouds, shade, outdoor lights, or a camera pointed at a bright bowl can all confuse fixed schedules.

## Power And USB Problems

If the feed says "no signal", freezes, or the camera disappears, check logs:

```bash
journalctl -k --since "2 hours ago" | grep -Ei 'usb|uvc|under.?voltage|thrott'
```

Undervoltage means the Pi's 5V rail is sagging. A high-wattage phone charger is not automatically enough; the Pi needs stable 5V at the board. Use a short power cable and consider a powered USB hub for the webcam.
