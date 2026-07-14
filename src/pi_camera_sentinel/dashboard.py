from __future__ import annotations

import datetime as dt
import io
import json
import logging
import math
import mimetypes
import socket
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunsplit

import requests
from PIL import Image, ImageStat

from . import __version__
from .camera import apply_profile, camera_state, set_controls
from .config import Settings
from .health import disk_status, recent_undervoltage_seen
from .masks import MAX_MOTION_MASKS, load_motion_masks, save_motion_masks, validate_motion_masks
from .policy import AlertPolicy, load_alert_policy, save_alert_policy
from .services import service_state, set_service_active


LOG = logging.getLogger("pi-camera-sentinel.dashboard")
STATIC_DIR = Path(__file__).with_name("static")
PROXY_HEADERS = {
    "cache-control",
    "content-length",
    "content-type",
    "expires",
    "pragma",
}
EVENT_WINDOWS = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "all": None,
}
MAX_EVENT_PAGE_SIZE = 48


def read_system_uptime() -> float | None:
    try:
        value = Path("/proc/uptime").read_text(encoding="ascii").split()[0]
        return round(float(value), 1)
    except (OSError, ValueError, IndexError):
        return None


def read_cpu_temperature() -> float | None:
    try:
        value = Path("/sys/class/thermal/thermal_zone0/temp").read_text(encoding="ascii").strip()
        return round(float(value) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def frame_luma(image: Image.Image) -> float:
    sample = image.convert("L")
    sample.thumbnail((320, 180), Image.Resampling.BILINEAR)
    return round(ImageStat.Stat(sample).mean[0], 1)


def collect_dashboard_status(
    settings: Settings,
    *,
    undervoltage_seen: bool | None,
    snapshot_get: Callable[..., requests.Response] = requests.get,
) -> dict:
    started = time.monotonic()
    feed: dict[str, object] = {
        "ok": False,
        "online": False,
        "status_code": None,
        "content_type": "",
        "width": None,
        "height": None,
        "frame_timestamp": None,
        "frame_age_seconds": None,
        "latency_ms": None,
        "dropped_frames": None,
        "mean_luma": None,
        "error": None,
    }
    warnings: list[str] = []

    try:
        response = snapshot_get(settings.snapshot_url, timeout=settings.http_timeout)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        image = Image.open(io.BytesIO(response.content))
        image.load()
        timestamp = response.headers.get("x-timestamp")
        frame_timestamp = float(timestamp) if timestamp else None
        dropped = response.headers.get("x-ustreamer-dropped")
        feed.update(
            {
                "ok": content_type.startswith("image/"),
                "online": response.headers.get("x-ustreamer-online", "true").lower() == "true",
                "status_code": response.status_code,
                "content_type": content_type,
                "width": image.width,
                "height": image.height,
                "frame_timestamp": frame_timestamp,
                "frame_age_seconds": (
                    round(max(0.0, time.time() - frame_timestamp), 2)
                    if frame_timestamp is not None
                    else None
                ),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "dropped_frames": int(dropped) if dropped is not None else None,
                "mean_luma": frame_luma(image),
            }
        )
    except (requests.RequestException, OSError, ValueError) as exc:
        feed["latency_ms"] = round((time.monotonic() - started) * 1000)
        feed["error"] = str(exc)
        warnings.append("camera snapshot is unavailable")

    camera_exists = settings.camera_device == "auto" or Path(settings.camera_device).exists()
    if not camera_exists:
        warnings.append(f"camera device not found: {settings.camera_device}")

    disk_path, disk_free_bytes, disk_total_bytes, disk_low = disk_status(
        settings.output_dir,
        settings.disk_min_free_mb,
    )
    if disk_low:
        warnings.append(f"less than {settings.disk_min_free_mb} MB of storage remains")
    if undervoltage_seen:
        warnings.append("recent Pi kernel logs report undervoltage")

    feed_ok = bool(feed["ok"] and feed["online"])
    if not feed_ok or not camera_exists:
        state = "offline"
    elif disk_low or undervoltage_seen:
        state = "degraded"
    else:
        state = "online"

    return {
        "version": __version__,
        "title": settings.dashboard_title,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "state": state,
        "ok": feed_ok and camera_exists and not disk_low,
        "feed": feed,
        "camera": {
            "device": settings.camera_device,
            "exists": camera_exists,
        },
        "system": {
            "hostname": socket.gethostname(),
            "uptime_seconds": read_system_uptime(),
            "temperature_c": read_cpu_temperature(),
            "undervoltage_seen": undervoltage_seen,
            "disk_path": str(disk_path),
            "disk_free_bytes": disk_free_bytes,
            "disk_total_bytes": disk_total_bytes,
            "disk_free_percent": round((disk_free_bytes / disk_total_bytes) * 100, 1),
            "disk_low": disk_low,
        },
        "warnings": warnings,
    }


def motion_event_records(directory: Path) -> list[tuple[Path, float, int]]:
    if not directory.exists():
        return []
    records: list[tuple[Path, float, int]] = []
    for path in directory.glob("motion-*"):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        records.append((path, stat.st_mtime, stat.st_size))
    return sorted(records, key=lambda record: (record[1], record[0].name), reverse=True)


def event_history(
    directory: Path,
    *,
    window: str = "24h",
    limit: int = 12,
    before: float | None = None,
    now: float | None = None,
) -> dict[str, object]:
    if window not in EVENT_WINDOWS:
        raise ValueError("window must be one of: 24h, 7d, all")
    if limit < 1 or limit > MAX_EVENT_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_EVENT_PAGE_SIZE}")
    if before is not None and (not math.isfinite(before) or before <= 0):
        raise ValueError("before must be a positive timestamp")

    records = motion_event_records(directory)
    current_time = time.time() if now is None else now
    window_seconds = EVENT_WINDOWS[window]
    cutoff = current_time - window_seconds if window_seconds is not None else None
    window_records = [record for record in records if cutoff is None or record[1] >= cutoff]
    candidates = [record for record in window_records if before is None or record[1] < before]
    page = candidates[:limit]
    has_more = len(candidates) > limit
    events = [
        {
            "name": path.name,
            "url": f"/events/{quote(path.name)}",
            "captured_at": dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat(),
            "size_bytes": size,
        }
        for path, timestamp, size in page
    ]

    return {
        "events": events,
        "window": window,
        "summary": {
            "window_count": len(window_records),
            "window_size_bytes": sum(record[2] for record in window_records),
            "retained_count": len(records),
            "retained_size_bytes": sum(record[2] for record in records),
            "last_captured_at": (
                dt.datetime.fromtimestamp(records[0][1], dt.timezone.utc).isoformat()
                if records
                else None
            ),
        },
        "next_before": page[-1][1] if has_more and page else None,
    }


def list_recent_events(directory: Path, limit: int = 12) -> list[dict[str, object]]:
    if limit <= 0:
        return []
    return event_history(directory, window="all", limit=limit)["events"]  # type: ignore[return-value]


def parse_event_query(query: str) -> tuple[str, int, float | None]:
    parameters = parse_qs(query, keep_blank_values=True)
    window = parameters.get("window", ["24h"])[0]
    try:
        limit = int(parameters.get("limit", ["12"])[0])
    except ValueError as exc:
        raise ValueError("limit must be an integer") from exc
    before_text = parameters.get("before", [""])[0]
    try:
        before = float(before_text) if before_text else None
    except ValueError as exc:
        raise ValueError("before must be a timestamp") from exc
    if window not in EVENT_WINDOWS:
        raise ValueError("window must be one of: 24h, 7d, all")
    if limit < 1 or limit > MAX_EVENT_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_EVENT_PAGE_SIZE}")
    if before is not None and (not math.isfinite(before) or before <= 0):
        raise ValueError("before must be a positive timestamp")
    return window, limit, before


def with_query(url: str, query: str) -> str:
    if not query:
        return url
    parts = urlsplit(url)
    combined = "&".join(value for value in (parts.query, query) if value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, combined, parts.fragment))


def same_origin(origin: str | None, host: str | None) -> bool:
    if not origin:
        return True
    if not host or origin == "null":
        return False
    try:
        return urlsplit(origin).netloc.lower() == host.lower()
    except ValueError:
        return False


class DashboardApplication:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._status: dict | None = None
        self._status_at = 0.0
        self._undervoltage: bool | None = None
        self._undervoltage_at = 0.0
        self._camera_lock = threading.RLock()
        self._mask_lock = threading.RLock()
        self._policy_lock = threading.RLock()
        self._service_lock = threading.RLock()

    def status(self) -> dict:
        now = time.monotonic()
        if self._status is not None and now - self._status_at < self.settings.dashboard_status_cache_seconds:
            return self._status
        if now - self._undervoltage_at >= 60:
            self._undervoltage = recent_undervoltage_seen()
            self._undervoltage_at = now
        self._status = collect_dashboard_status(
            self.settings,
            undervoltage_seen=self._undervoltage,
        )
        self._status_at = now
        return self._status

    def events(
        self,
        *,
        window: str,
        limit: int,
        before: float | None,
    ) -> dict[str, object]:
        return event_history(
            self.settings.output_dir,
            window=window,
            limit=limit,
            before=before,
        )

    def camera(self) -> dict[str, object]:
        with self._camera_lock:
            return camera_state(self.settings.camera_device)

    def apply_camera_profile(self, profile: str) -> dict[str, object]:
        with self._camera_lock:
            apply_profile(self.settings.camera_device, profile)
            return camera_state(self.settings.camera_device)

    def update_camera_controls(self, values: dict[str, int]) -> dict[str, object]:
        with self._camera_lock:
            return set_controls(self.settings.camera_device, values)

    def alert_policy(self) -> dict[str, object]:
        with self._policy_lock:
            policy = load_alert_policy(self.settings.policy_file)
            return policy.to_dict(self.settings.timezone)

    def update_alert_policy(self, payload: dict) -> dict[str, object]:
        with self._policy_lock:
            policy = AlertPolicy.from_dict(payload)
            state = policy.to_dict(self.settings.timezone)
            save_alert_policy(self.settings.policy_file, policy)
            return state

    def motion_masks(self) -> dict[str, object]:
        with self._mask_lock:
            masks = load_motion_masks(self.settings.mask_file)
            return {
                "regions": [mask.to_dict() for mask in masks],
                "max_regions": MAX_MOTION_MASKS,
            }

    def update_motion_masks(self, payload: dict) -> dict[str, object]:
        with self._mask_lock:
            masks = validate_motion_masks(payload.get("regions"))
            save_motion_masks(self.settings.mask_file, masks)
            return {
                "regions": [mask.to_dict() for mask in masks],
                "max_regions": MAX_MOTION_MASKS,
            }

    def services(self) -> dict[str, dict[str, object]]:
        with self._service_lock:
            return {
                "motion": service_state(self.settings.motion_service),
                "watchdog": service_state(self.settings.exposure_service),
            }

    def update_service(self, service_id: str, active: bool) -> dict[str, object]:
        service_names = {
            "motion": self.settings.motion_service,
            "watchdog": self.settings.exposure_service,
        }
        try:
            service_name = service_names[service_id]
        except KeyError as exc:
            raise ValueError("unknown service") from exc
        with self._service_lock:
            return set_service_active(service_name, active)


class DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], app: DashboardApplication):
        self.app = app
        super().__init__(server_address, DashboardRequestHandler)

    def handle_error(self, request: object, client_address: tuple[str, int]) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            LOG.debug("dashboard client %s disconnected", client_address[0])
            return
        super().handle_error(request, client_address)


class DashboardRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = f"PiCameraSentinel/{__version__}"

    @property
    def app(self) -> DashboardApplication:
        return self.server.app  # type: ignore[attr-defined, no-any-return]

    def log_message(self, format_string: str, *args: object) -> None:
        LOG.debug("%s - %s", self.client_address[0], format_string % args)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def send_bytes(
        self,
        status: HTTPStatus,
        content_type: str,
        body: bytes,
        *,
        cache_control: str = "no-store",
        content_disposition: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        if content_disposition:
            self.send_header("Content-Disposition", content_disposition)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_bytes(status, "application/json; charset=utf-8", body)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/":
            self.serve_static("index.html")
        elif path.startswith("/assets/"):
            self.serve_static(path.removeprefix("/assets/"))
        elif path == "/api/status":
            self.send_json(self.app.status())
        elif path == "/api/events":
            try:
                window, limit, before = parse_event_query(parsed.query)
                self.send_json(self.app.events(window=window, limit=limit, before=before))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        elif path == "/api/camera":
            self.send_camera_state()
        elif path == "/api/policy":
            self.send_policy_state()
        elif path == "/api/masks":
            self.send_motion_masks_state()
        elif path == "/api/services":
            self.send_json({"services": self.app.services()})
        elif path == "/healthz":
            payload = self.app.status()
            status = HTTPStatus.OK if payload["ok"] else HTTPStatus.SERVICE_UNAVAILABLE
            self.send_json(payload, status)
        elif path == "/stream":
            self.proxy_stream(parsed.query)
        elif path == "/snapshot":
            download = parse_qs(parsed.query).get("download") == ["1"]
            self.proxy_snapshot(parsed.query, download=download)
        elif path.startswith("/events/"):
            self.serve_event(unquote(path.removeprefix("/events/")))
        else:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not same_origin(self.headers.get("Origin"), self.headers.get("Host")):
            self.send_json({"error": "cross-origin changes are not allowed"}, HTTPStatus.FORBIDDEN)
            return
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        path = urlsplit(self.path).path
        if path == "/api/camera/profile":
            profile = payload.get("profile")
            if not isinstance(profile, str):
                self.send_json({"error": "profile must be a string"}, HTTPStatus.BAD_REQUEST)
                return
            self.run_camera_action(lambda: self.app.apply_camera_profile(profile))
        elif path == "/api/camera/controls":
            controls = payload.get("controls")
            if not isinstance(controls, dict):
                self.send_json({"error": "controls must be an object"}, HTTPStatus.BAD_REQUEST)
                return
            self.run_camera_action(lambda: self.app.update_camera_controls(controls))
        elif path == "/api/policy":
            self.run_policy_action(lambda: self.app.update_alert_policy(payload))
        elif path == "/api/masks":
            self.run_motion_masks_action(lambda: self.app.update_motion_masks(payload))
        elif path.startswith("/api/services/"):
            service_id = path.removeprefix("/api/services/")
            active = payload.get("active")
            if not isinstance(active, bool):
                self.send_json({"error": "active must be a boolean"}, HTTPStatus.BAD_REQUEST)
                return
            self.run_service_action(lambda: self.app.update_service(service_id, active))
        else:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def read_json_body(self) -> dict:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("request content type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length <= 0 or length > 8192:
            raise ValueError("request body must be between 1 and 8192 bytes")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def send_camera_state(self) -> None:
        self.run_camera_action(self.app.camera)

    def send_policy_state(self) -> None:
        try:
            self.send_json(self.app.alert_policy())
        except (OSError, ValueError) as exc:
            LOG.warning("alert policy read failed: %s", exc)
            self.send_json({"error": "alert policy is unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def send_motion_masks_state(self) -> None:
        try:
            self.send_json(self.app.motion_masks())
        except (OSError, ValueError) as exc:
            LOG.warning("motion mask read failed: %s", exc)
            self.send_json({"error": "motion masks are unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_camera_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, subprocess.SubprocessError) as exc:
            LOG.warning("camera control action failed: %s", exc)
            self.send_json({"error": "camera controls are unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_service_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, subprocess.SubprocessError) as exc:
            LOG.warning("service control action failed: %s", exc)
            self.send_json({"error": "service control is unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_policy_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            LOG.warning("alert policy write failed: %s", exc)
            self.send_json({"error": "alert policy is unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def run_motion_masks_action(self, action: Callable[[], dict[str, object]]) -> None:
        try:
            self.send_json(action())
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            LOG.warning("motion mask write failed: %s", exc)
            self.send_json({"error": "motion masks are unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def serve_static(self, name: str) -> None:
        target = (STATIC_DIR / name).resolve()
        if target.parent != STATIC_DIR.resolve() or not target.is_file():
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_bytes(
            HTTPStatus.OK,
            content_type,
            target.read_bytes(),
            cache_control="public, max-age=300" if target.name != "index.html" else "no-cache",
        )

    def serve_event(self, name: str) -> None:
        directory = self.app.settings.output_dir.resolve()
        target = (directory / name).resolve()
        if target.parent != directory or not target.is_file() or not target.name.startswith("motion-"):
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_bytes(HTTPStatus.OK, content_type, target.read_bytes(), cache_control="private, max-age=3600")

    def copy_proxy_headers(self, response: requests.Response) -> None:
        for name, value in response.headers.items():
            if name.lower() in PROXY_HEADERS or name.lower().startswith("x-ustreamer-") or name.lower() == "x-timestamp":
                self.send_header(name, value)

    def proxy_snapshot(self, query: str, *, download: bool) -> None:
        try:
            response = requests.get(
                with_query(self.app.settings.snapshot_url, query),
                timeout=self.app.settings.http_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.send_json({"error": f"snapshot upstream unavailable: {exc}"}, HTTPStatus.BAD_GATEWAY)
            return
        self.send_response(response.status_code)
        self.copy_proxy_headers(response)
        if download:
            stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
            self.send_header("Content-Disposition", f'attachment; filename="sentinel-{stamp}.jpg"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response.content)

    def proxy_stream(self, query: str) -> None:
        response_started = False
        try:
            with requests.get(
                with_query(self.app.settings.stream_url, query),
                stream=True,
                timeout=(self.app.settings.http_timeout, None),
            ) as response:
                response.raise_for_status()
                self.send_response(response.status_code)
                self.copy_proxy_headers(response)
                self.send_header("Connection", "close")
                self.end_headers()
                response_started = True
                if self.command == "HEAD":
                    return
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        self.wfile.write(chunk)
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            LOG.debug("stream client disconnected")
        except requests.RequestException as exc:
            if response_started:
                LOG.debug("stream connection ended: %s", exc)
            else:
                LOG.warning("stream upstream unavailable: %s", exc)
                self.send_json({"error": f"stream upstream unavailable: {exc}"}, HTTPStatus.BAD_GATEWAY)


def serve_dashboard(settings: Settings) -> None:
    app = DashboardApplication(settings)
    server = DashboardHTTPServer((settings.dashboard_host, settings.dashboard_port), app)
    LOG.info(
        "dashboard listening on http://%s:%s with stream upstream %s",
        settings.dashboard_host,
        settings.dashboard_port,
        settings.stream_url,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        LOG.info("stopping dashboard")
    finally:
        server.server_close()
