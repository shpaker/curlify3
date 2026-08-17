# curlify3

Convert request objects from popular Python HTTP libraries into ready-to-run `curl` commands.

[![PyPI](https://img.shields.io/pypi/v/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Downloads](https://img.shields.io/pypi/dm/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Python](https://img.shields.io/pypi/pyversions/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Tests](https://github.com/shpaker/curlify3/actions/workflows/tests.yml/badge.svg)](https://github.com/shpaker/curlify3/actions/workflows/tests.yml)

`curlify3` takes a request object from any supported client or server framework and renders it as an equivalent `curl` command — useful for logging, debugging, sharing reproductions, and copy-pasting from your IDE into a terminal.

## Features

- Single dispatch entrypoint — `to_curl()` (sync) and `to_curl_async()` (async)
- Works with **client-side** requests (`requests`, `httpx`, `httpx2`) and **server-side** incoming requests (`aiohttp.web`, `starlette` / `fastapi`)
- Faithful rendering of headers, query parameters, cookies (`-b`), and bodies
- Body payloads: text, JSON, form-encoded, multipart, binary
- POSIX shell output by default, Windows PowerShell output with `shell="powershell"`
- Zero runtime dependencies

## Installation

```sh
pip install curlify3
```

Requires **Python 3.10+**.

## Comparison with `curlify` and `curlify2`

| | [`curlify`](https://pypi.org/project/curlify/) | [`curlify2`](https://pypi.org/project/curlify2/) | **`curlify3`** |
| --- | :---: | :---: | :---: |
| `requests` | [x] | [x] | [x] |
| `httpx` | [ ] | [x] | [x] |
| `httpx2` (HTTP/2) | [ ] | [ ] | [x] |
| `aiohttp` (server-side) | [ ] | [ ] | [x] |
| `starlette` / `fastapi` (server-side) | [ ] | [ ] | [x] |
| Async API | [ ] | [ ] | [x] |
| Python | 3.7+ | 3.7–3.11 | 3.10+ |

`curlify` is the original and covers only `requests`. `curlify2` added `httpx` but is sync-only, client-side-only, and has not seen a release since 2023. `curlify3` extends the same idea with HTTP/2 (`httpx2`), an async entrypoint, and server-side adapters for `aiohttp` and `starlette` / `fastapi` so you can dump incoming requests as `curl` from inside a handler.

## Quick start

```python
import requests
from curlify3 import to_curl

response = requests.get("https://httpbin.org/get")
print(to_curl(response.request))
# curl -H 'user-agent: python-requests/2.32.3' -H 'accept-encoding: gzip, deflate' \
#      -H 'accept: */*' -H 'connection: keep-alive' https://httpbin.org/get
```

## Usage

### `requests`

```python
import requests
from curlify3 import to_curl

req = requests.Request(
    "POST",
    "https://httpbin.org/post",
    json={"hello": "world"},
).prepare()

print(to_curl(req))
```

### `httpx` (sync)

```python
import httpx
from curlify3 import to_curl

req = httpx.Request("POST", "https://httpbin.org/post", json={"hello": "world"})
print(to_curl(req))
```

### `httpx` (async)

```python
import asyncio
import httpx
from curlify3 import to_curl_async

async def main():
    req = httpx.Request("POST", "https://httpbin.org/post", json={"a": 1})
    print(await to_curl_async(req))

asyncio.run(main())
```

### `httpx2` — HTTP/2

The generated command includes `--http2`.

```python
import httpx2
from curlify3 import to_curl

req = httpx2.Request("GET", "https://httpbin.org/get")
print(to_curl(req))
# curl --http2 -H 'host: httpbin.org' https://httpbin.org/get
```

`to_curl_async()` works with `httpx2.Request` too.

### Windows PowerShell

By default the command is formatted for POSIX shells. Pass `shell="powershell"` to get a command that pastes cleanly into Windows PowerShell / `pwsh`: the binary becomes `curl.exe` (plain `curl` is an alias for `Invoke-WebRequest` in Windows PowerShell), single quotes are escaped by doubling, and embedded double quotes are escaped as `\"` so JSON payloads survive PowerShell's argument passing to native executables.

```python
import requests
from curlify3 import to_curl

req = requests.Request(
    "POST",
    "https://httpbin.org/post",
    json={"date": "2026-08-10"},
).prepare()

print(to_curl(req, shell="powershell"))
# curl.exe -X POST -H 'content-type: application/json' -d '{\"date\": \"2026-08-10\"}' https://httpbin.org/post
```

The constants `curlify3.SH` and `curlify3.POWERSHELL` are exported for use instead of the raw strings.

### `aiohttp` — server-side

Render an incoming request inside a handler. The async variant is required because the body is read from the stream.

```python
from aiohttp import web
from curlify3 import to_curl_async

async def handler(request: web.Request) -> web.Response:
    curl = await to_curl_async(request)
    print(curl)
    return web.json_response({"ok": True})
```

### `starlette` / `fastapi` — server-side

```python
from fastapi import FastAPI, Request
from curlify3 import to_curl_async

app = FastAPI()

@app.post("/echo")
async def echo(request: Request):
    curl = await to_curl_async(request)
    return {"curl": curl}
```

## API

### `to_curl(request, shell="sh") -> str`

Render a request object as a `curl` command. Use for synchronous request types (`requests.PreparedRequest`, `httpx.Request`, `httpx2.Request`).

### `to_curl_async(request, shell="sh") -> str`

Async variant. Use for server-side request objects whose body must be `await`-ed (`aiohttp.web.Request`, `starlette.requests.Request`) or when you prefer the async pathway for `httpx` / `httpx2`.

`shell` selects the output dialect: `"sh"` (default, POSIX shells) or `"powershell"` (Windows PowerShell / `pwsh`).

Both functions raise `ValueError` if the request type or the `shell` value is not recognized.

## Supported request objects

| Library | Type | `to_curl` | `to_curl_async` | Notes |
| --- | --- | :---: | :---: | --- |
| `requests` | `PreparedRequest` | [x] | [ ] | Pass `Request(...).prepare()` |
| `httpx` | `httpx.Request` | [x] | [x] | |
| `httpx2` | `httpx2.Request` | [x] | [x] | Adds `--http2` |
| `aiohttp` | `aiohttp.web.Request` | [ ] | [x] | Server-side |
| `starlette` / `fastapi` | `starlette.requests.Request` | [ ] | [x] | Server-side |

## Payload handling

| Payload | Rendered as |
| --- | --- |
| Plain text | `-d 'text'` |
| JSON | `-d '{"k":"v"}'` with `content-type: application/json` |
| Form-encoded | `-d 'k=v&k2=v2'` with `content-type: application/x-www-form-urlencoded` |
| Multipart / files | `-F 'field=@file' -F 'other=value'` |
| Binary | `-d` with raw bytes (falls back when not UTF-8) |
| Cookies | `-b 'k=v'` (lifted out of `Cookie` header) |
| Headers | `-H 'name: value'` (lowercased) |

`Content-Length` is dropped. If a body is present without `Content-Type`, `content-type: plain/text` is added so `curl` does not guess.

## Development

The project uses [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/).

```sh
uv sync --group dev
just tests   # uv run pytest -vv
just fmt     # isort + black
```

CI runs the test suite on Python 3.10–3.14.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
