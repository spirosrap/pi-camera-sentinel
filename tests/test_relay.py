import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

import requests
from PIL import Image, ImageStat

from pi_camera_sentinel.relay import JpegColorCorrection, RelayHTTPServer, RelaySettings
from pi_camera_sentinel.redirect import redirect_location


def jpeg_bytes(color=(100, 80, 100)):
    output = BytesIO()
    Image.new("RGB", (32, 24), color).save(
        output,
        format="JPEG",
        quality=100,
        subsampling=0,
    )
    return output.getvalue()


def mean_rgb(payload):
    with Image.open(BytesIO(payload)) as image:
        return ImageStat.Stat(image.convert("RGB")).mean


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"path": self.path, "source": "dashboard"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = json.dumps(
            {
                "host": self.headers.get("Host"),
                "origin": self.headers.get("Origin"),
                "path": self.path,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class CameraHandler(BaseHTTPRequestHandler):
    stream_lock = threading.Lock()
    stream_requests = 0

    def do_GET(self):
        if self.path.startswith("/snapshot"):
            body = b"snapshot-bytes"
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-UStreamer-Online", "true")
            self.end_headers()
            self.wfile.write(body)
            return

        with self.stream_lock:
            type(self).stream_requests += 1
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=camera")
        self.send_header("X-UStreamer-Online", "true")
        self.end_headers()
        try:
            for index in range(100):
                frame = (
                    b"\xff\xd8"
                    + f"frame-{index}:".encode()
                    + (b"x" * 8192)
                    + b"\xff\xd9"
                )
                part = (
                    b"--camera\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(frame)).encode()
                    + b"\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
                self.wfile.write(part)
                self.wfile.flush()
                time.sleep(0.02)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_args):
        pass


class RecoveringCameraHandler(BaseHTTPRequestHandler):
    stream_lock = threading.Lock()
    stream_requests = 0

    def do_GET(self):
        with self.stream_lock:
            type(self).stream_requests += 1
            generation = type(self).stream_requests
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=camera")
        self.end_headers()
        frame = (
            b"\xff\xd8"
            + f"generation-{generation}:".encode()
            + (b"x" * 8192)
            + b"\xff\xd9"
        )
        part = (
            b"--camera\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(frame)).encode()
            + b"\r\n\r\n"
            + frame
            + b"\r\n"
        )
        try:
            self.wfile.write(part)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_args):
        pass


class ColorCameraHandler(BaseHTTPRequestHandler):
    frame = jpeg_bytes()

    def do_GET(self):
        if self.path.startswith("/snapshot"):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(self.frame)))
            self.end_headers()
            self.wfile.write(self.frame)
            return

        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=camera")
        self.end_headers()
        part = (
            b"--camera\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(self.frame)).encode()
            + b"\r\n\r\n"
            + self.frame
            + b"\r\n"
        )
        try:
            for _ in range(20):
                self.wfile.write(part)
                self.wfile.flush()
                time.sleep(0.02)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_args):
        pass


@contextmanager
def running_server(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def relay_stack():
    CameraHandler.stream_requests = 0
    dashboard = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    camera = ThreadingHTTPServer(("127.0.0.1", 0), CameraHandler)
    dashboard_url = f"http://127.0.0.1:{dashboard.server_port}"
    camera_url = f"http://127.0.0.1:{camera.server_port}"
    settings = RelaySettings(
        host="127.0.0.1",
        port=0,
        dashboard_url=dashboard_url,
        stream_url=f"{camera_url}/stream",
        snapshot_url=f"{camera_url}/snapshot",
    )
    relay = RelayHTTPServer((settings.host, settings.port), settings)
    return dashboard, camera, relay


def read_one_frame(response):
    payload = bytearray()
    for chunk in response.iter_content(chunk_size=256):
        payload.extend(chunk)
        start = payload.find(b"\xff\xd8")
        end = payload.find(b"\xff\xd9", start + 2) if start >= 0 else -1
        if start >= 0 and end >= 0:
            return bytes(payload[start : end + 2])
    raise AssertionError("stream ended before a JPEG frame arrived")


def read_frames(response, count):
    payload = bytearray()
    frames = []
    for chunk in response.iter_content(chunk_size=256):
        payload.extend(chunk)
        while len(frames) < count:
            start = payload.find(b"\xff\xd8")
            end = payload.find(b"\xff\xd9", start + 2) if start >= 0 else -1
            if start < 0 or end < 0:
                break
            frames.append(bytes(payload[start : end + 2]))
            del payload[: end + 2]
        if len(frames) == count:
            return frames
    raise AssertionError(f"stream ended after {len(frames)} of {count} JPEG frames")


def test_relay_routes_dashboard_and_media_without_reencoding():
    dashboard, camera, relay = relay_stack()
    with running_server(dashboard), running_server(camera), running_server(relay):
        base = f"http://127.0.0.1:{relay.server_port}"

        status = requests.get(f"{base}/api/status?detail=1", timeout=2)
        snapshot = requests.get(f"{base}/snapshot?download=1", timeout=2)
        with requests.get(
            f"{base}/stream?advance_headers=1",
            timeout=2,
            stream=True,
        ) as stream:
            stream_frame = read_one_frame(stream)
            stream_content_type = stream.headers["Content-Type"]

    assert status.json() == {"path": "/api/status?detail=1", "source": "dashboard"}
    assert snapshot.content == b"snapshot-bytes"
    assert snapshot.headers["X-UStreamer-Online"] == "true"
    assert snapshot.headers["Content-Disposition"].startswith("attachment;")
    assert stream_content_type == "multipart/x-mixed-replace; boundary=sentinelframe"
    assert stream_frame.startswith(b"\xff\xd8frame-")
    assert stream_frame.endswith(b"\xff\xd9")


def test_relay_fans_multiple_viewers_out_from_one_camera_stream():
    dashboard, camera, relay = relay_stack()
    assert relay.shared_stream.idle_timeout == 30.0
    with running_server(dashboard), running_server(camera), running_server(relay):
        base = f"http://127.0.0.1:{relay.server_port}"
        first = requests.get(f"{base}/stream?viewer=1", timeout=2, stream=True)
        second = requests.get(f"{base}/stream?viewer=2", timeout=2, stream=True)
        try:
            assert read_one_frame(first).startswith(b"\xff\xd8frame-")
            assert read_one_frame(second).startswith(b"\xff\xd8frame-")
            assert CameraHandler.stream_requests == 1
        finally:
            first.close()
            second.close()


def test_relay_keeps_viewer_attached_while_camera_stream_reconnects():
    RecoveringCameraHandler.stream_requests = 0
    dashboard = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    camera = ThreadingHTTPServer(("127.0.0.1", 0), RecoveringCameraHandler)
    camera_url = f"http://127.0.0.1:{camera.server_port}"
    settings = RelaySettings(
        host="127.0.0.1",
        port=0,
        dashboard_url=f"http://127.0.0.1:{dashboard.server_port}",
        stream_url=f"{camera_url}/stream",
        snapshot_url=f"{camera_url}/snapshot",
        connect_timeout=0.5,
        stream_read_timeout=0.5,
        stream_client_timeout=3,
    )
    relay = RelayHTTPServer((settings.host, settings.port), settings)

    with running_server(dashboard), running_server(camera), running_server(relay):
        base = f"http://127.0.0.1:{relay.server_port}"
        with requests.get(f"{base}/stream", timeout=(2, 4), stream=True) as stream:
            frames = read_frames(stream, 2)

    assert b"generation-1:" in frames[0]
    assert b"generation-2:" in frames[1]
    assert RecoveringCameraHandler.stream_requests >= 2


def test_relay_color_correction_applies_to_snapshot_and_stream():
    dashboard = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    camera = ThreadingHTTPServer(("127.0.0.1", 0), ColorCameraHandler)
    camera_url = f"http://127.0.0.1:{camera.server_port}"
    settings = RelaySettings(
        host="127.0.0.1",
        port=0,
        dashboard_url=f"http://127.0.0.1:{dashboard.server_port}",
        stream_url=f"{camera_url}/stream",
        snapshot_url=f"{camera_url}/snapshot",
        green_gain=1.5,
        jpeg_quality=95,
    )
    relay = RelayHTTPServer((settings.host, settings.port), settings)

    with running_server(dashboard), running_server(camera), running_server(relay):
        base = f"http://127.0.0.1:{relay.server_port}"
        snapshot = requests.get(f"{base}/snapshot?download=1", timeout=2)
        with requests.get(f"{base}/stream", timeout=2, stream=True) as stream:
            stream_frame = read_one_frame(stream)

    source_mean = mean_rgb(ColorCameraHandler.frame)
    for corrected in (snapshot.content, stream_frame):
        corrected_mean = mean_rgb(corrected)
        assert corrected_mean[1] > source_mean[1] + 30
        assert abs(corrected_mean[0] - source_mean[0]) < 5
        assert abs(corrected_mean[2] - source_mean[2]) < 5
    assert snapshot.headers["Content-Disposition"].startswith("attachment;")


def test_disabled_color_correction_preserves_original_jpeg_bytes():
    frame = jpeg_bytes()
    assert JpegColorCorrection().apply(frame) is frame


def test_relay_rewrites_host_and_origin_for_dashboard_writes():
    dashboard, camera, relay = relay_stack()
    with running_server(dashboard), running_server(camera), running_server(relay):
        base = f"http://127.0.0.1:{relay.server_port}"
        response = requests.post(
            f"{base}/api/policy",
            json={"enabled": True},
            headers={"Origin": "https://relay.example"},
            timeout=2,
        )

    payload = response.json()
    expected_authority = f"127.0.0.1:{dashboard.server_port}"
    assert payload["path"] == "/api/policy"
    assert payload["host"] == expected_authority
    assert payload["origin"] == f"http://{expected_authority}"


def test_retired_camera_url_preserves_path_and_query_on_relay():
    assert redirect_location(
        "https://relay.example/",
        "/stream?advance_headers=1",
    ) == "https://relay.example/stream?advance_headers=1"
