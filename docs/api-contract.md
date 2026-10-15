# URL-shortener API contract

The local API uses JSON for request and response bodies. It has no authentication in this assessment prototype and should bind to loopback by default.

## Create a short URL

`POST /api/shorten`

Request:

```json
{
  "url": "https://example.com/article"
}
```

The body must be a JSON object containing only `url`. The value must be an absolute HTTP(S) URL, at most 2,048 characters, with no embedded username/password credentials.

Successful response (`201 Created`):

```json
{
  "code": "aB3dE9x",
  "short_url": "http://localhost:8000/aB3dE9x",
  "destination": "https://example.com/article",
  "created_at": "2026-10-12T12:00:00+00:00"
}
```

Errors include `400 Bad Request` for malformed JSON, unexpected request properties, or invalid destination; `413 Content Too Large` for bodies over 16 KiB; and `503 Service Unavailable` if the bounded short-code allocation attempts are exhausted.

## Redirect

`GET /{code}`

`code` is seven alphanumeric characters. On success the API atomically increments the click count and returns `302 Found` with the destination in the `Location` header. Unknown or malformed codes return `404 Not Found`.

## Analytics

`GET /api/analytics/{code}`

Successful response (`200 OK`):

```json
{
  "code": "aB3dE9x",
  "destination": "https://example.com/article",
  "created_at": "2026-10-12T12:00:00+00:00",
  "click_count": 3,
  "last_accessed_at": "2026-10-12T12:15:00+00:00"
}
```

Unknown or malformed codes return `404 Not Found`.

## Health

`GET /healthz` returns `200 OK` with `{"status":"ok"}` while the process can serve requests.

## Error shape

All JSON error responses use:

```json
{
  "error": {
    "code": "invalid_destination",
    "message": "Destination must be an HTTP or HTTPS URL without embedded credentials."
  }
}
```

The API intentionally does not support custom codes, link expiration, authentication, or analytics beyond aggregate click count and last-access time.
