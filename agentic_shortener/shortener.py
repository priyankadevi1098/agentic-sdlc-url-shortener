from __future__ import annotations

import re
import secrets
import string
from urllib.parse import urlsplit

from .storage import CodeConflictError, UrlStore

_CODE_ALPHABET = string.ascii_letters + string.digits
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{7}$")
_MAX_DESTINATION_LENGTH = 2048
_MAX_CODE_ATTEMPTS = 5


class InvalidDestinationError(ValueError):
    pass


class ShortUrlNotFoundError(LookupError):
    pass


class ShortCodeAllocationError(RuntimeError):
    pass


class ShortenerService:
    def __init__(self, store: UrlStore) -> None:
        self.store = store

    def shorten(self, destination: str, base_url: str) -> dict[str, object]:
        self._validate_destination(destination)
        for _ in range(_MAX_CODE_ATTEMPTS):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(7))
            try:
                self.store.create(code, destination)
                record = self.store.get(code)
                if record is None:
                    raise RuntimeError("Created short URL could not be retrieved.")
                return {
                    "code": code,
                    "short_url": f"{base_url.rstrip('/')}/{code}",
                    "destination": destination,
                    "created_at": record["created_at"],
                }
            except CodeConflictError:
                continue
        raise ShortCodeAllocationError(
            "Could not allocate a unique short code after bounded retries."
        )

    def resolve(self, code: str) -> str:
        if not _CODE_PATTERN.fullmatch(code):
            raise ShortUrlNotFoundError(code)
        destination = self.store.record_click(code)
        if destination is None:
            raise ShortUrlNotFoundError(code)
        return destination

    def analytics(self, code: str) -> dict[str, object]:
        if not _CODE_PATTERN.fullmatch(code):
            raise ShortUrlNotFoundError(code)
        record = self.store.get(code)
        if record is None:
            raise ShortUrlNotFoundError(code)
        return record

    @staticmethod
    def _validate_destination(destination: str) -> None:
        if not isinstance(destination, str) or not destination.strip():
            raise InvalidDestinationError("A destination URL is required.")
        if len(destination) > _MAX_DESTINATION_LENGTH:
            raise InvalidDestinationError("The destination URL is too long.")
        try:
            parsed = urlsplit(destination)
        except ValueError as error:
            raise InvalidDestinationError("Destination must be a valid HTTP or HTTPS URL.") from error
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise InvalidDestinationError(
                "Destination must be an HTTP or HTTPS URL without embedded credentials."
            )
