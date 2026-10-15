from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from agentic_shortener.api import create_server
from agentic_shortener.shortener import (
    InvalidDestinationError,
    ShortUrlNotFoundError,
    ShortenerService,
)
from agentic_shortener.storage import UrlStore


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class ShortenerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = UrlStore(Path(self.temporary_directory.name) / "test.sqlite3")
        self.service = ShortenerService(self.store)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_shorten_persists_destination_and_returns_code(self) -> None:
        result = self.service.shorten("https://example.com/path", "http://localhost:8000")

        self.assertEqual(result["short_url"], f"http://localhost:8000/{result['code']}")
        self.assertEqual(self.service.analytics(str(result["code"]))["destination"], "https://example.com/path")

    def test_rejects_non_http_url_and_embedded_credentials(self) -> None:
        for value in ("javascript:alert(1)", "https://user:secret@example.com", "http://[bad"):
            with self.subTest(value=value), self.assertRaises(InvalidDestinationError):
                self.service.shorten(value, "http://localhost:8000")

    def test_resolve_increments_click_analytics(self) -> None:
        result = self.service.shorten("https://example.com", "http://localhost:8000")

        self.assertEqual(self.service.resolve(str(result["code"])), "https://example.com")
        analytics = self.service.analytics(str(result["code"]))
        self.assertEqual(analytics["click_count"], 1)
        self.assertIsNotNone(analytics["last_accessed_at"])

    def test_unknown_short_code_is_not_found(self) -> None:
        with self.assertRaises(ShortUrlNotFoundError):
            self.service.resolve("missing1")


class ShortenerHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        store = UrlStore(Path(self.temporary_directory.name) / "test.sqlite3")
        self.server = create_server(
            ShortenerService(store), "127.0.0.1", 0, "http://127.0.0.1"
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"
        self.no_redirect = build_opener(NoRedirectHandler())

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary_directory.cleanup()

    def test_create_redirect_and_analytics_http_flow(self) -> None:
        body = json.dumps({"url": "https://example.com/article"}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/shorten",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 201)
            result = json.load(response)

        with self.assertRaises(HTTPError) as redirect_error:
            self.no_redirect.open(f"{self.base_url}/{result['code']}", timeout=3)
        self.assertEqual(redirect_error.exception.code, 302)
        self.assertEqual(redirect_error.exception.headers["Location"], "https://example.com/article")
        redirect_error.exception.close()

        with urlopen(f"{self.base_url}/api/analytics/{result['code']}", timeout=3) as response:
            analytics = json.load(response)
        self.assertEqual(analytics["click_count"], 1)

    def test_invalid_create_request_returns_client_error(self) -> None:
        for payload in (
            {"url": "file:///etc/passwd"},
            {"url": "https://example.com", "unexpected": True},
        ):
            request = Request(
                f"{self.base_url}/api/shorten",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with self.subTest(payload=payload), self.assertRaises(HTTPError) as error:
                urlopen(request, timeout=3)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()


if __name__ == "__main__":
    unittest.main()
