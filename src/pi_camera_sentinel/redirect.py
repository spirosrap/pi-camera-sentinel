from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit

from .relay import port_number, validated_http_url


LOG = logging.getLogger("pi-camera-sentinel.redirect")


@dataclass(frozen=True)
class RedirectSettings:
    host: str
    port: int
    target_url: str

    @classmethod
    def from_env(cls) -> "RedirectSettings":
        return cls(
            host=os.environ.get("SENTINEL_REDIRECT_HOST", "127.0.0.1"),
            port=port_number(
                os.environ.get("SENTINEL_REDIRECT_PORT", "8092"),
                "SENTINEL_REDIRECT_PORT",
            ),
            target_url=validated_http_url(
                os.environ.get("SENTINEL_REDIRECT_TARGET_URL", ""),
                "SENTINEL_REDIRECT_TARGET_URL",
            ),
        )


def redirect_location(target_url: str, request_target: str) -> str:
    target = urlsplit(target_url)
    request = urlsplit(request_target)
    request_path = request.path if request.path.startswith("/") else "/"
    prefix = target.path.rstrip("/")
    return urlunsplit(
        (
            target.scheme,
            target.netloc,
            f"{prefix}{request_path}" or "/",
            request.query,
            "",
        )
    )


class RedirectHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "PiCameraSentinelRedirect/1"

    def do_HEAD(self) -> None:
        self.send_redirect()

    def do_GET(self) -> None:
        self.send_redirect()

    def do_POST(self) -> None:
        self.send_redirect()

    def send_redirect(self) -> None:
        target_url = getattr(self.server, "target_url")
        location = redirect_location(target_url, self.path)
        self.send_response(HTTPStatus.TEMPORARY_REDIRECT)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        LOG.debug("%s - %s", self.address_string(), format % args)


def serve_redirect(settings: RedirectSettings) -> None:
    server = ThreadingHTTPServer((settings.host, settings.port), RedirectHandler)
    server.target_url = settings.target_url
    LOG.info(
        "redirect listening on http://%s:%s -> %s",
        settings.host,
        settings.port,
        settings.target_url,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        LOG.info("stopping redirect")
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Redirect a retired Sentinel URL to its relay host.")
    parser.add_argument(
        "--log-level",
        default=os.environ.get("SENTINEL_REDIRECT_LOG_LEVEL", "INFO"),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = RedirectSettings.from_env()
    except ValueError as exc:
        parser.error(str(exc))
    serve_redirect(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
