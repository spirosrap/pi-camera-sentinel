from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit, urlunsplit

import requests


LOG = logging.getLogger("pi-camera-sentinel.relay")
COPY_CHUNK_SIZE = 64 * 1024
MAX_REQUEST_BODY = 1024 * 1024
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
GENERATED_RESPONSE_HEADERS = {"date", "server"}


def positive_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def port_number(value: str, name: str = "SENTINEL_RELAY_PORT") -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return port


def validated_http_url(value: str, name: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError(f"{name} must not contain credentials or a fragment")
    return value


@dataclass(frozen=True)
class RelaySettings:
    host: str
    port: int
    dashboard_url: str
    stream_url: str
    snapshot_url: str
    connect_timeout: float = 5.0
    request_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "RelaySettings":
        return cls(
            host=os.environ.get("SENTINEL_RELAY_HOST", "127.0.0.1"),
            port=port_number(os.environ.get("SENTINEL_RELAY_PORT", "8091")),
            dashboard_url=validated_http_url(
                os.environ.get("SENTINEL_RELAY_DASHBOARD_URL", ""),
                "SENTINEL_RELAY_DASHBOARD_URL",
            ),
            stream_url=validated_http_url(
                os.environ.get("SENTINEL_RELAY_STREAM_URL", ""),
                "SENTINEL_RELAY_STREAM_URL",
            ),
            snapshot_url=validated_http_url(
                os.environ.get("SENTINEL_RELAY_SNAPSHOT_URL", ""),
                "SENTINEL_RELAY_SNAPSHOT_URL",
            ),
            connect_timeout=positive_float(
                os.environ.get("SENTINEL_RELAY_CONNECT_TIMEOUT", "5"),
                "SENTINEL_RELAY_CONNECT_TIMEOUT",
            ),
            request_timeout=positive_float(
                os.environ.get("SENTINEL_RELAY_REQUEST_TIMEOUT", "30"),
                "SENTINEL_RELAY_REQUEST_TIMEOUT",
            ),
        )


@dataclass(frozen=True)
class RelayTarget:
    url: str
    kind: str


def with_request_path(base_url: str, path: str, query: str) -> str:
    parsed = urlsplit(base_url)
    prefix = parsed.path.rstrip("/")
    request_path = path if path.startswith("/") else f"/{path}"
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            f"{prefix}{request_path}" or "/",
            query,
            "",
        )
    )


def with_request_query(base_url: str, query: str) -> str:
    parsed = urlsplit(base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def relay_target(settings: RelaySettings, path: str, query: str) -> RelayTarget:
    if path == "/stream":
        return RelayTarget(with_request_query(settings.stream_url, query), "stream")
    if path == "/snapshot":
        return RelayTarget(with_request_query(settings.snapshot_url, query), "snapshot")
    return RelayTarget(with_request_path(settings.dashboard_url, path, query), "dashboard")


def upstream_request_headers(headers: object, target_url: str) -> dict[str, str]:
    target = urlsplit(target_url)
    forwarded: dict[str, str] = {}
    for name, value in getattr(headers, "items")():
        lower = name.lower()
        if lower in HOP_BY_HOP_HEADERS or lower in {"host", "content-length"}:
            continue
        if lower.startswith("x-forwarded-"):
            continue
        forwarded[name] = value

    upstream_origin = f"{target.scheme}://{target.netloc}"
    forwarded["Host"] = target.netloc
    if getattr(headers, "get")("Origin"):
        forwarded["Origin"] = upstream_origin
    if getattr(headers, "get")("Referer"):
        forwarded["Referer"] = f"{upstream_origin}/"
    forwarded["X-Forwarded-Host"] = getattr(headers, "get")("Host", "")
    return forwarded


class RelayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64

    def __init__(self, server_address: tuple[str, int], settings: RelaySettings):
        self.settings = settings
        super().__init__(server_address, RelayRequestHandler)

    def handle_error(self, request: object, client_address: tuple[str, int]) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            LOG.debug("client connection ended: %s", client_address[0])
            return
        super().handle_error(request, client_address)


class RelayRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "PiCameraSentinelRelay/1"

    @property
    def relay_server(self) -> RelayHTTPServer:
        return self.server  # type: ignore[return-value]

    def do_HEAD(self) -> None:
        self.proxy_request()

    def do_GET(self) -> None:
        self.proxy_request()

    def do_POST(self) -> None:
        self.proxy_request()

    def read_request_body(self) -> bytes | None:
        if self.command not in {"POST", "PUT", "PATCH"}:
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length < 0 or length > MAX_REQUEST_BODY:
            raise ValueError(f"request body exceeds {MAX_REQUEST_BODY} bytes")
        return self.rfile.read(length)

    def send_json_error(self, status: HTTPStatus, message: str) -> None:
        body = json.dumps({"error": message}, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def proxy_request(self) -> None:
        parsed = urlsplit(self.path)
        target = relay_target(self.relay_server.settings, parsed.path, parsed.query)
        try:
            body = self.read_request_body()
        except ValueError as exc:
            self.send_json_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        response_started = False
        timeout: tuple[float, float | None] = (
            self.relay_server.settings.connect_timeout,
            None if target.kind == "stream" else self.relay_server.settings.request_timeout,
        )
        try:
            with requests.request(
                self.command,
                target.url,
                headers=upstream_request_headers(self.headers, target.url),
                data=body,
                allow_redirects=False,
                stream=True,
                timeout=timeout,
            ) as response:
                response.raw.decode_content = False
                self.send_response(response.status_code)
                response_has_length = False
                has_content_disposition = False
                for name, value in response.headers.items():
                    lower = name.lower()
                    if lower in HOP_BY_HOP_HEADERS or lower in GENERATED_RESPONSE_HEADERS:
                        continue
                    response_has_length = response_has_length or lower == "content-length"
                    has_content_disposition = has_content_disposition or lower == "content-disposition"
                    self.send_header(name, value)

                if (
                    target.kind == "snapshot"
                    and not has_content_disposition
                    and parse_qs(parsed.query).get("download") == ["1"]
                ):
                    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="sentinel-{stamp}.jpg"',
                    )
                if target.kind == "stream" or not response_has_length:
                    self.send_header("Connection", "close")
                    self.close_connection = True
                self.end_headers()
                response_started = True
                if self.command == "HEAD":
                    return

                while True:
                    chunk = response.raw.read(COPY_CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    if target.kind == "stream":
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            LOG.debug("%s client disconnected", target.kind)
        except requests.RequestException as exc:
            if response_started:
                LOG.debug("%s upstream connection ended: %s", target.kind, exc)
            else:
                LOG.warning("%s upstream unavailable: %s", target.kind, exc)
                self.send_json_error(
                    HTTPStatus.BAD_GATEWAY,
                    f"{target.kind} upstream unavailable",
                )

    def log_message(self, format: str, *args: object) -> None:
        LOG.debug("%s - %s", self.address_string(), format % args)


def serve_relay(settings: RelaySettings) -> None:
    server = RelayHTTPServer((settings.host, settings.port), settings)
    LOG.info(
        "relay listening on http://%s:%s; dashboard=%s stream=%s",
        settings.host,
        settings.port,
        settings.dashboard_url,
        settings.stream_url,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        LOG.info("stopping relay")
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Relay Pi Camera Sentinel through a more capable Tailscale host."
    )
    parser.add_argument("--log-level", default=os.environ.get("SENTINEL_RELAY_LOG_LEVEL", "INFO"))
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = RelaySettings.from_env()
    except ValueError as exc:
        parser.error(str(exc))
    serve_relay(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
