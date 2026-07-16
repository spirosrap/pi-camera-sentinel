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

from .batching import MotionBatch, MotionSample, validate_batch_config
from .camera import PROFILES, apply_profile, controls_json, list_controls
from .config import Settings
from .dashboard import serve_dashboard
from .exposure import exposure_watchdog_step
from .health import check_health
from .masks import MotionMask, load_motion_masks
from .motion import changed_pixel_ratio, fetch_snapshot, normalize_image, summarize_ratios
from .policy import load_alert_policy
from .recovery import (
    RecoveryState,
    load_recovery_state,
    recovery_watchdog_step,
    save_recovery_state,
    validate_recovery_config,
)
from .recovery_alerts import initialize_recovery_alert_cursor, process_recovery_alerts
from .retention import RetentionPolicy, enforce_retention, policy_from_settings
from .telegram import get_chat_ids, send_media_group, send_message, send_photo, send_video
from .webhook import deliver_webhook, webhook_payload


LOG = logging.getLogger("pi-camera-sentinel")


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def caption(
    settings: Settings,
    ratio: float | None = None,
    captured_at: dt.datetime | None = None,
) -> str:
    current = captured_at or dt.datetime.now().astimezone()
    text = f"Motion detected at {current.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    if ratio is not None:
        text += f"\nChanged pixels: {ratio:.1%}"
    if settings.feed_url:
        text += f"\nLive feed: {settings.feed_url}"
    return text


def batch_caption(settings: Settings, batch: MotionBatch) -> str:
    if batch.first_captured_at is None:
        raise ValueError("motion batch has no capture timestamp")
    if batch.detection_count == 1:
        return caption(settings, batch.peak_ratio, batch.first_captured_at)

    duration = max(1, round(batch.duration_seconds))
    text = f"Motion burst: {batch.detection_count} detections over {duration}s"
    text += f"\nFirst seen: {batch.first_captured_at.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    text += f"\nPeak changed pixels: {batch.peak_ratio:.1%}"
    if settings.feed_url:
        text += f"\nLive feed: {settings.feed_url}"
    return text


def cleanup_old_files(directory: Path, max_files: int) -> None:
    enforce_retention(directory, RetentionPolicy(max_files=max_files))


def cleanup_archive(settings: Settings) -> None:
    result = enforce_retention(settings.output_dir, policy_from_settings(settings))
    if result.removed:
        LOG.info(
            "archive retention removed files=%s bytes=%s",
            len(result.removed),
            sum(removal.file.size_bytes for removal in result.removed),
        )
    if result.errors:
        LOG.warning("archive retention could not remove: %s", ", ".join(result.errors))


def refresh_motion_masks(
    settings: Settings,
    current: tuple[MotionMask, ...],
    previous_error: str | None,
) -> tuple[tuple[MotionMask, ...], str | None]:
    try:
        loaded = load_motion_masks(settings.mask_file)
    except (OSError, ValueError) as exc:
        message = str(exc)
        if message != previous_error:
            LOG.warning("could not reload motion masks; keeping last valid set: %s", message)
        return current, message
    if previous_error is not None:
        LOG.info("motion mask configuration is readable again")
    if loaded != current:
        LOG.info("motion masks updated count=%s", len(loaded))
    return loaded, None


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


def archive_motion_batch(settings: Settings, batch: MotionBatch) -> list[Path]:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, sample in enumerate(batch.samples):
        stamp = sample.captured_at.strftime("%Y%m%d-%H%M%S-%f")
        path = settings.output_dir / f"motion-{stamp}.jpg"
        if path.exists():
            path = settings.output_dir / f"motion-{stamp}-{index + 1}.jpg"
        path.write_bytes(sample.snapshot)
        paths.append(path)
    return paths


def handle_motion_batch(settings: Settings, batch: MotionBatch) -> None:
    if not batch.samples or batch.first_captured_at is None:
        raise ValueError("motion batch contains no samples")

    photo_paths = archive_motion_batch(settings, batch)
    event_caption = batch_caption(settings, batch)
    LOG.info(
        "motion batch: detections=%s photos=%s peak_ratio=%.4f duration=%.1fs",
        batch.detection_count,
        len(photo_paths),
        batch.peak_ratio,
        batch.duration_seconds,
    )

    try:
        quiet_now = load_alert_policy(settings.policy_file).quiet_now(settings.timezone)
    except (OSError, ValueError) as exc:
        LOG.warning("could not evaluate alert policy; notifications remain enabled: %s", exc)
        quiet_now = False

    try:
        if quiet_now:
            LOG.info("Telegram batch suppressed by quiet hours; captures remain archived")
        else:
            if settings.send_photo:
                if len(photo_paths) > 1:
                    send_media_group(settings, photo_paths, event_caption)
                else:
                    send_photo(settings, photo_paths[0], event_caption)
            else:
                send_message(settings, event_caption)

            if settings.send_video:
                stamp = batch.first_captured_at.strftime("%Y%m%d-%H%M%S-%f")
                video_path = settings.output_dir / f"motion-{stamp}.mp4"
                if record_video_clip(settings, video_path):
                    send_video(settings, video_path, f"Motion clip\n{settings.feed_url}")
    finally:
        if settings.webhook_url:
            try:
                status_code = deliver_webhook(
                    settings,
                    webhook_payload(
                        settings,
                        event="motion",
                        captured_at=batch.first_captured_at,
                        ratio=batch.peak_ratio,
                        capture_path=photo_paths[0],
                        batch_count=batch.detection_count,
                        batch_duration_seconds=batch.duration_seconds,
                        batch_capture_paths=photo_paths,
                    ),
                )
                LOG.info("Home Assistant webhook delivered status=%s", status_code)
            except Exception as exc:
                LOG.warning("Home Assistant webhook delivery failed: %s", exc)
        cleanup_archive(settings)


def handle_motion_event(settings: Settings, snapshot: bytes, ratio: float) -> None:
    sample = MotionSample(snapshot, ratio, dt.datetime.now().astimezone())
    batch = MotionBatch.start(
        sample,
        now=time.monotonic(),
        window_seconds=0,
        max_photos=1,
    )
    handle_motion_batch(settings, batch)


def cmd_monitor(settings: Settings, _args: argparse.Namespace) -> int:
    missing = settings.missing_telegram_fields()
    if missing:
        LOG.error("missing Telegram config fields: %s", ", ".join(missing))
        return 2
    try:
        validate_batch_config(settings.alert_batch_seconds, settings.alert_batch_max_photos)
        policy_from_settings(settings)
    except ValueError as exc:
        LOG.error("invalid motion monitor configuration: %s", exc)
        return 2

    session = requests.Session()
    previous = None
    consecutive = 0
    last_alert = 0.0
    batch: MotionBatch | None = None
    masks, mask_error = refresh_motion_masks(settings, (), None)
    masks_checked_at = time.monotonic()
    LOG.info(
        "monitoring %s threshold=%s ratio=%.4f min_frames=%s cooldown=%ss batch=%ss/%s photos",
        settings.snapshot_url,
        settings.diff_threshold,
        settings.changed_ratio,
        settings.min_motion_frames,
        settings.cooldown_seconds,
        settings.alert_batch_seconds,
        settings.alert_batch_max_photos,
    )

    while True:
        try:
            now = time.monotonic()
            if batch is not None and batch.due(now):
                ready_batch = batch
                batch = None
                last_alert = now
                handle_motion_batch(settings, ready_batch)

            snapshot, image = fetch_snapshot(session, settings)
            current = normalize_image(image, settings)
            if previous is None:
                previous = current
                time.sleep(settings.poll_seconds)
                continue

            now = time.monotonic()
            if now - masks_checked_at >= 5:
                previous_masks = masks
                masks, mask_error = refresh_motion_masks(settings, masks, mask_error)
                masks_checked_at = now
                if masks != previous_masks:
                    consecutive = 0

            ratio = changed_pixel_ratio(previous, current, settings.diff_threshold, masks)
            if ratio >= settings.changed_ratio:
                consecutive += 1
                LOG.info("motion candidate ratio=%.4f frame=%s/%s", ratio, consecutive, settings.min_motion_frames)
            else:
                consecutive = 0

            if consecutive >= settings.min_motion_frames:
                sample = MotionSample(snapshot, ratio, dt.datetime.now().astimezone())
                if batch is not None:
                    batch.add(sample)
                    LOG.info(
                        "motion added to batch detection=%s photos=%s/%s",
                        batch.detection_count,
                        len(batch.samples),
                        batch.max_photos,
                    )
                elif now - last_alert >= settings.cooldown_seconds:
                    if settings.alert_batch_seconds == 0:
                        handle_motion_event(settings, snapshot, ratio)
                        last_alert = now
                    else:
                        batch = MotionBatch.start(
                            sample,
                            now=now,
                            window_seconds=settings.alert_batch_seconds,
                            max_photos=settings.alert_batch_max_photos,
                        )
                        LOG.info(
                            "motion batch started window=%ss photo_limit=%s",
                            settings.alert_batch_seconds,
                            settings.alert_batch_max_photos,
                        )
                consecutive = 0

            previous = current
            time.sleep(settings.poll_seconds)
        except KeyboardInterrupt:
            if batch is not None:
                LOG.info("flushing pending motion batch detections=%s", batch.detection_count)
                try:
                    handle_motion_batch(settings, batch)
                except Exception:
                    LOG.exception("pending motion batch delivery failed during shutdown")
            LOG.info("stopping")
            return 0
        except Exception:
            LOG.exception("monitor loop error")
            time.sleep(max(settings.poll_seconds, 5.0))


def cmd_sample(settings: Settings, args: argparse.Namespace) -> int:
    session = requests.Session()
    previous = None
    ratios: list[float] = []
    masks, _mask_error = refresh_motion_masks(settings, (), None)
    for index in range(args.frames):
        _, image = fetch_snapshot(session, settings)
        current = normalize_image(image, settings)
        if previous is not None:
            ratio = changed_pixel_ratio(previous, current, settings.diff_threshold, masks)
            ratios.append(ratio)
            print(json.dumps({"frame": index, "changed_ratio": ratio}, sort_keys=True))
        previous = current
        time.sleep(settings.poll_seconds)
    summary = summarize_ratios(ratios)
    summary["configured_trigger_ratio"] = settings.changed_ratio
    summary["diff_threshold"] = settings.diff_threshold
    summary["masked_regions"] = len(masks)
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


def cmd_send_webhook_test(settings: Settings, _args: argparse.Namespace) -> int:
    try:
        status_code = deliver_webhook(
            settings,
            webhook_payload(
                settings,
                event="test",
                captured_at=dt.datetime.now().astimezone(),
            ),
        )
    except (requests.RequestException, ValueError) as exc:
        LOG.error("Home Assistant webhook test failed: %s", exc)
        return 2
    print(json.dumps({"ok": True, "status_code": status_code}, sort_keys=True))
    return 0


def cmd_show_chat_ids(settings: Settings, _args: argparse.Namespace) -> int:
    for chat in get_chat_ids(settings):
        print(json.dumps(chat, sort_keys=True))
    return 0


def cmd_health(settings: Settings, _args: argparse.Namespace) -> int:
    result = check_health(settings)
    print(result.to_json())
    return 0 if result.ok else 1


def cmd_retention_cleanup(settings: Settings, args: argparse.Namespace) -> int:
    try:
        result = enforce_retention(
            settings.output_dir,
            policy_from_settings(settings),
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        LOG.error("invalid archive retention configuration: %s", exc)
        return 2
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 1 if result.errors else 0


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


def cmd_exposure_step(settings: Settings, args: argparse.Namespace) -> int:
    result = exposure_watchdog_step(settings)
    if args.json:
        print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


def cmd_exposure_watchdog(settings: Settings, _args: argparse.Namespace) -> int:
    LOG.info(
        "starting exposure watchdog interval=%ss snapshot=%s",
        settings.exposure_watchdog_interval,
        settings.snapshot_url,
    )
    while True:
        try:
            exposure_watchdog_step(settings)
        except KeyboardInterrupt:
            LOG.info("stopping")
            return 0
        except Exception:
            LOG.exception("exposure watchdog cycle failed")
        time.sleep(settings.exposure_watchdog_interval)


def recovery_state_or_default(settings: Settings) -> RecoveryState:
    try:
        return load_recovery_state(
            settings.recovery_state_file,
            stream_service=settings.stream_service,
        )
    except (OSError, ValueError) as exc:
        LOG.warning("recovery state is unreadable; starting fresh: %s", exc)
        return RecoveryState(stream_service=settings.stream_service)


def prepared_recovery_state(settings: Settings) -> RecoveryState:
    state = recovery_state_or_default(settings)
    prepared = initialize_recovery_alert_cursor(state)
    if prepared != state:
        save_recovery_state(settings.recovery_state_file, prepared)
    return prepared


def recovery_step_with_alerts(settings: Settings) -> RecoveryState:
    result = recovery_watchdog_step(settings, prepared_recovery_state(settings))
    try:
        return process_recovery_alerts(settings, result)
    except Exception as exc:
        LOG.warning("feed recovery Telegram alert failed; delivery will retry: %s", exc)
        return result


def cmd_recovery_step(settings: Settings, args: argparse.Namespace) -> int:
    try:
        validate_recovery_config(settings)
    except ValueError as exc:
        LOG.error("invalid feed recovery configuration: %s", exc)
        return 2
    result = recovery_step_with_alerts(settings)
    if args.json:
        print(json.dumps(result.to_dict(), sort_keys=True))
    return 1 if result.status == "failed" else 0


def cmd_recovery_watchdog(settings: Settings, _args: argparse.Namespace) -> int:
    try:
        validate_recovery_config(settings)
    except ValueError as exc:
        LOG.error("invalid feed recovery configuration: %s", exc)
        return 2
    missing_telegram = settings.missing_telegram_fields()
    telegram_alerts = settings.recovery_telegram_alerts and not missing_telegram
    if settings.recovery_telegram_alerts and missing_telegram:
        LOG.warning(
            "feed recovery Telegram alerts disabled; missing: %s",
            ", ".join(missing_telegram),
        )
    LOG.info(
        "starting feed recovery interval=%ss failures=%s stale=%ss cooldown=%ss stream=%s telegram_alerts=%s",
        settings.recovery_interval_seconds,
        settings.recovery_failure_threshold,
        settings.recovery_stale_seconds,
        settings.recovery_cooldown_seconds,
        settings.stream_service,
        "on" if telegram_alerts else "off",
    )
    while True:
        try:
            state = recovery_step_with_alerts(settings)
            LOG.info(
                "feed recovery status=%s failures=%s restarts=%s reason=%s",
                state.status,
                state.consecutive_failures,
                state.restart_count,
                state.last_reason,
            )
        except KeyboardInterrupt:
            LOG.info("stopping")
            return 0
        except Exception:
            LOG.exception("feed recovery cycle failed")
        time.sleep(settings.recovery_interval_seconds)


def cmd_serve(settings: Settings, _args: argparse.Namespace) -> int:
    serve_dashboard(settings)
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
    subparsers.add_parser("send-webhook-test", help="send one test event to the configured webhook").set_defaults(
        func=cmd_send_webhook_test
    )
    subparsers.add_parser("show-chat-ids", help="print chat IDs from recent bot updates").set_defaults(func=cmd_show_chat_ids)
    subparsers.add_parser("healthcheck", help="check snapshot, camera, power, and storage status").set_defaults(func=cmd_health)
    retention = subparsers.add_parser(
        "retention-cleanup",
        help="apply local motion archive retention limits",
    )
    retention.add_argument("--dry-run", action="store_true", help="report candidates without deleting files")
    retention.set_defaults(func=cmd_retention_cleanup)
    subparsers.add_parser("serve", help="serve the web dashboard and camera proxy").set_defaults(func=cmd_serve)
    subparsers.add_parser("camera-controls", help="list v4l2 camera controls").set_defaults(func=cmd_camera_controls)
    subparsers.add_parser("camera-get", help="print common camera controls as JSON").set_defaults(func=cmd_camera_get)

    exposure_once = subparsers.add_parser("exposure-step", help="sample the image once and apply day/night profile if needed")
    exposure_once.add_argument("--json", action="store_true", help="print decision as JSON")
    exposure_once.set_defaults(func=cmd_exposure_step)

    subparsers.add_parser("exposure-watchdog", help="continuously adjust camera profile when image is too dark or washed out").set_defaults(
        func=cmd_exposure_watchdog
    )

    recovery_once = subparsers.add_parser(
        "recovery-step",
        help="check feed health once and restart a failed stream when required",
    )
    recovery_once.add_argument("--json", action="store_true", help="print recovery state as JSON")
    recovery_once.set_defaults(func=cmd_recovery_step)

    subparsers.add_parser(
        "recovery-watchdog",
        help="continuously recover an unavailable or stale camera feed",
    ).set_defaults(func=cmd_recovery_watchdog)

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
