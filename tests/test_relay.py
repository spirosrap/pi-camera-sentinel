import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from pi_camera_sentinel.relay import RelayHTTPServer, RelaySettings
from pi_camera_sentinel.redirect import redirect_location


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
    def do_GET(self):
        body = b"snapshot-bytes" if self.path.startswith("/snapshot") else b"mjpeg-bytes"
        content_type = "image/jpeg" if self.path.startswith("/snapshot") else "multipart/x-mixed-replace"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-UStreamer-Online", "true")
        self.end_headers()
        self.wfile.write(body)

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


def test_relay_routes_dashboard_and_media_without_reencoding():
    dashboard, camera, relay = relay_stack()
    with running_server(dashboard), running_server(camera), running_server(relay):
        base = f"http://127.0.0.1:{relay.server_port}"

        status = requests.get(f"{base}/api/status?detail=1", timeout=2)
        snapshot = requests.get(f"{base}/snapshot?download=1", timeout=2)
        stream = requests.get(f"{base}/stream?advance_headers=1", timeout=2)

    assert status.json() == {"path": "/api/status?detail=1", "source": "dashboard"}
    assert snapshot.content == b"snapshot-bytes"
    assert snapshot.headers["X-UStreamer-Online"] == "true"
    assert snapshot.headers["Content-Disposition"].startswith("attachment;")
    assert stream.content == b"mjpeg-bytes"


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
