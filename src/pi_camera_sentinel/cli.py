from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import requests

from .camera import PROFILES, apply_profile, controls_json, list_controls
from .config import Settings
from .health import check_health
from .motion import changed_pixel_ratio, fetch_snapshot, normalize_image, summarize_ratios
from .telegram import get_chat_ids, send_message, send_photo, send_video


LOG = logging.getLogger("pi-camera-sentinel")


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def caption(settings: Settings, ratio: float | None = None) -> str:
    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    text = f"Motion detected at {now}"
    if ratio is not None:
        text += f"\nChanged pixels: {ratio:.1%}"
    if settings.feed_url:
        text += f"\nLive feed: {settings.feed_url}"
    return text


def cleanup_old_files(directory: Path, max_files: int) -> None:
    if max_files <= 0:
        return
    files = sorted(
        [path for path in directory.glob("motion-*") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in files[max_files:]:
        try:
            old.unlink()
        except OSError as exc:
            LOG.debug("could not remove old file %s: %s", old, exc)


def record_video_clip(settings: Settings, path: Path) -> bool:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-t",
        str(settings.video_seconds),
        "-i",
        settings.stream_url,
        "-an",
        "-vf",
        f"fps={settings.video_fps},scale=640:-2",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    try:
        subprocess.run(command, check=True, timeout=settings.video_seconds + 25)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        LOG.warning("video recording failed: %s", exc)
        return False
    return path.exists() and path.stat().st_size > 0


def handle_motion_event(settings: Settings, snapshot: bytes, ratio: float) -> None:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    photo_path = settings.output_dir / f"motion-{stamp}.jpg"
    photo_path.write_bytes(snapshot)
    event_caption = caption(settings, ratio)
    LOG.info("motion event: ratio=%.4f photo=%s", ratio, photo_path)

    if settings.send_photo:
        send_photo(settings, photo_path, event_caption)
    else:
        send_message(settings, event_caption)

    if settings.send_video:
        video_path = settings.output_dir / f"motion-{stamp}.mp4"
        if record_video_clip(settings, video_path):
            send_video(settings, video_path, f"Motion clip\n{settings.feed_url}")

    cleanup_old_files(settings.output_dir, settings.retention_files)


def cmd_monitor(settings: Settings, _args: argparse.Namespace) -> int:
    missing = settings.missing_telegram_fields()
    if missing:
        LOG.error("missing Telegram config fields: %s", ", ".join(missing))
        return 2

    session = requests.Session()
    previous = None
    consecutive = 0
    last_alert = 0.0
    LOG.info(
        "monitoring %s threshold=%s ratio=%.4f min_frames=%s cooldown=%ss",
        settings.snapshot_url,
        settings.diff_threshold,
        settings.changed_ratio,
        settings.min_motion_frames,
        settings.cooldown_seconds,
    )

    while True:
        try:
            snapshot, image = fetch_snapshot(session, settings)
            current = normalize_image(image, settings)
            if previous is None:
                previous = current
                time.sleep(settings.poll_seconds)
                continue

            ratio = changed_pixel_ratio(previous, current, settings.diff_threshold)
            if ratio >= settings.changed_ratio:
                consecutive += 1
                LOG.info("motion candidate ratio=%.4f frame=%s/%s", ratio, consecutive, settings.min_motion_frames)
            else:
                consecutive = 0

            now = time.monotonic()
            if consecutive >= settings.min_motion_frames and now - last_alert >= settings.cooldown_seconds:
                handle_motion_event(settings, snapshot, ratio)
                last_alert = now
                consecutive = 0

            previous = current
            time.sleep(settings.poll_seconds)
        except KeyboardInterrupt:
            LOG.info("stopping")
            return 0
        except Exception:
            LOG.exception("monitor loop error")
            time.sleep(max(settings.poll_seconds, 5.0))


def cmd_sample(settings: Settings, args: argparse.Namespace) -> int:
    session = requests.Session()
    previous = None
    ratios: list[float] = []
    for index in range(args.frames):
        _, image = fetch_snapshot(session, settings)
        current = normalize_image(image, settings)
        if previous is not None:
            ratio = changed_pixel_ratio(previous, current, settings.diff_threshold)
            ratios.append(ratio)
            print(json.dumps({"frame": index, "changed_ratio": ratio}, sort_keys=True))
        previous = current
        time.sleep(settings.poll_seconds)
    summary = summarize_ratios(ratios)
    summary["configured_trigger_ratio"] = settings.changed_ratio
    summary["diff_threshold"] = settings.diff_threshold
    print(json.dumps(summary, sort_keys=True))
    return 0


def cmd_send_test(settings: Settings, _args: argparse.Namespace) -> int:
    missing = settings.missing_telegram_fields()
    if missing:
        LOG.error("missing Telegram config fields: %s", ", ".join(missing))
        return 2
    session = requests.Session()
    snapshot, _ = fetch_snapshot(session, settings)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    path = settings.output_dir / "telegram-test.jpg"
    path.write_bytes(snapshot)
    send_photo(settings, path, f"Test alert\nLive feed: {settings.feed_url}")
    LOG.info("sent Telegram test photo")
    return 0


def cmd_show_chat_ids(settings: Settings, _args: argparse.Namespace) -> int:
    for chat in get_chat_ids(settings):
        print(json.dumps(chat, sort_keys=True))
    return 0


def cmd_health(settings: Settings, _args: argparse.Namespace) -> int:
    result = check_health(settings)
    print(result.to_json())
    return 0 if result.ok else 1


def cmd_camera_profile(settings: Settings, args: argparse.Namespace) -> int:
    controls = apply_profile(settings.camera_device, args.profile)
    print(json.dumps({"device": settings.camera_device, "profile": args.profile, "controls": controls}, sort_keys=True))
    return 0


def cmd_camera_controls(settings: Settings, _args: argparse.Namespace) -> int:
    print(list_controls(settings.camera_device))
    return 0


def cmd_camera_get(settings: Settings, _args: argparse.Namespace) -> int:
    names = [
        "brightness",
        "contrast",
        "saturation",
        "white_balance_automatic",
        "white_balance_temperature",
        "gain",
        "backlight_compensation",
        "power_line_frequency",
        "auto_exposure",
        "exposure_time_absolute",
    ]
    print(controls_json(settings.camera_device, names))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Private Raspberry Pi USB camera sentinel.")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("monitor", help="run motion detector and Telegram sender").set_defaults(func=cmd_monitor)

    sample = subparsers.add_parser("sample", help="sample N frames and print motion ratios")
    sample.add_argument("frames", type=int, nargs="?", default=10)
    sample.set_defaults(func=cmd_sample)

    subparsers.add_parser("send-test", help="send one test snapshot to Telegram").set_defaults(func=cmd_send_test)
    subparsers.add_parser("show-chat-ids", help="print chat IDs from recent bot updates").set_defaults(func=cmd_show_chat_ids)
    subparsers.add_parser("healthcheck", help="check snapshot, camera, and undervoltage status").set_defaults(func=cmd_health)
    subparsers.add_parser("camera-controls", help="list v4l2 camera controls").set_defaults(func=cmd_camera_controls)
    subparsers.add_parser("camera-get", help="print common camera controls as JSON").set_defaults(func=cmd_camera_get)

    profile = subparsers.add_parser("camera-profile", help="apply a named v4l2 camera profile")
    profile.add_argument("profile", choices=sorted(PROFILES))
    profile.set_defaults(func=cmd_camera_profile)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    settings = Settings.from_env()
    return args.func(settings, args)


if __name__ == "__main__":
    sys.exit(main())
