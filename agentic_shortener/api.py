from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .shortener import (
    InvalidDestinationError,
    ShortCodeAllocationError,
    ShortUrlNotFoundError,
    ShortenerService,
)

_MAX_BODY_BYTES = 16_384
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{7}$")


class ShortenerHandler(BaseHTTPRequestHandler):
    service: ShortenerService
    base_url: str
    server_version = "AssessmentShortener/0.1"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._write_json(HTTPStatus.OK, {"status": "ok"})
            return

        analytics_match = re.fullmatch(r"/api/analytics/([A-Za-z0-9]+)", path)
        if analytics_match:
            self._handle_analytics(analytics_match.group(1))
            return

        code = path.lstrip("/")
        if code and "/" not in code and _CODE_PATTERN.fullmatch(code):
            self._handle_redirect(code)
            return
        self._write_error(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/shorten":
            self._write_error(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")
            return

        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._write_error(HTTPStatus.LENGTH_REQUIRED, "length_required", "Content-Length is required.")
            return
        try:
            body_size = int(content_length)
        except ValueError:
            self._write_error(HTTPStatus.BAD_REQUEST, "invalid_content_length", "Content-Length must be an integer.")
            return
        if body_size < 0 or body_size > _MAX_BODY_BYTES:
            self._write_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large", "Request body is too large.")
            return

        try:
            payload = json.loads(self.rfile.read(body_size))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._write_error(HTTPStatus.BAD_REQUEST, "invalid_json", "Request body must be valid JSON.")
            return
        if not isinstance(payload, dict):
            self._write_error(HTTPStatus.BAD_REQUEST, "invalid_body", "Request body must be a JSON object.")
            return
        if set(payload) != {"url"}:
            self._write_error(
                HTTPStatus.BAD_REQUEST,
                "invalid_body",
                "Request body must contain only the url property.",
            )
            return

        try:
            response = self.service.shorten(payload.get("url"), self.base_url)
        except InvalidDestinationError as error:
            self._write_error(HTTPStatus.BAD_REQUEST, "invalid_destination", str(error))
            return
        except ShortCodeAllocationError:
            self._write_error(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "short_code_unavailable",
                "A short code could not be allocated. Retry the request.",
            )
            return
        self._write_json(HTTPStatus.CREATED, response)

    def _handle_redirect(self, code: str) -> None:
        try:
            destination = self.service.resolve(code)
        except ShortUrlNotFoundError:
            self._write_error(HTTPStatus.NOT_FOUND, "not_found", "Short URL was not found.")
            return
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", destination)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _handle_analytics(self, code: str) -> None:
        try:
            analytics = self.service.analytics(code)
        except ShortUrlNotFoundError:
            self._write_error(HTTPStatus.NOT_FOUND, "not_found", "Short URL was not found.")
            return
        self._write_json(HTTPStatus.OK, analytics)

    def _write_error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._write_json(status, {"error": {"code": code, "message": message}})

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.log_date_time_string()} {format % args}")


def create_server(
    service: ShortenerService, host: str, port: int, base_url: str
) -> ThreadingHTTPServer:
    handler = type(
        "BoundShortenerHandler",
        (ShortenerHandler,),
        {"service": service, "base_url": base_url},
    )
    return ThreadingHTTPServer((host, port), handler)
