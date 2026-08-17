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
- Faithful rendering of headers, query parameters, cookies (`-b`), and bodies, quoted so the command survives the shell even when the values came from an untrusted client
- Body payloads: text, JSON, form-encoded, multipart, binary
- POSIX shell output by default, Windows PowerShell output with `shell="powershell"`
- One-line output by default, multi-line with `pretty=True` and long option names with `long_options=True`
- Zero runtime dependencies
- Fully annotated and `py.typed`, so the types reach your own type checker

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

### Readable output

`pretty=True` puts every option on its own line, and `long_options=True` spells the options out (`--header` instead of `-H`). They are independent, so either can be used alone.

```python
import requests
from curlify3 import to_curl

req = requests.Request(
    "POST",
    "https://httpbin.org/post",
    json={"date": "2026-08-10"},
).prepare()

print(to_curl(req, pretty=True, long_options=True))
# curl https://httpbin.org/post \
#   --request POST \
#   --header 'content-type: application/json' \
#   --data '{"date": "2026-08-10"}'
```

The url moves to the first line, where `curl` reads it just as well as in the trailing position — the same layout Chrome DevTools' "Copy as cURL" produces. A request with no options stays on one line.

`pretty=True` is rejected with a `ValueError` for `shell="powershell"`: the `--%` token that dialect relies on is effective only until the next newline, and a backtick cannot extend it, so a multi-line command would be passed to `curl.exe` in pieces.

### Quoting, and untrusted values

Every rendered value is quoted for the target shell, so a body, header, cookie or url is data and never becomes part of the command. This matters most for the server-side adapters, where all of those arrive from the client:

```python
# an incoming request whose path and cookie were chosen by the caller
print(await to_curl_async(request))
# curl -b 'n=O'\''Brien' -H 'host: example.com' 'http://example.com/x;id'
```

The url and the cookie header are left bare when every character in them is safe, which is the common case and keeps the command short. Anything else is quoted — including the `?` of a single-parameter query string, which `zsh` would otherwise reject as an unmatched glob.

### Windows PowerShell

By default the command is formatted for POSIX shells. Pass `shell="powershell"` to get one that pastes into Windows PowerShell 5.1.

```python
import requests
from curlify3 import to_curl

req = requests.Request(
    "POST",
    "https://httpbin.org/post",
    json={"date": "2026-08-10"},
).prepare()

print(to_curl(req, shell="powershell"))
# curl.exe --% -X POST -H "content-type: application/json" -d "{\"date\": \"2026-08-10\"}" "https://httpbin.org/post"
```

`curl.exe` avoids the `Invoke-WebRequest` alias, and `--%` — PowerShell's stop-parsing token — hands the rest to `curl.exe` verbatim. The token is what makes arbitrary JSON survive: without it, 5.1's argument binder re-quotes values by counting every double quote, escaped or not, and mangles the body. Two consequences worth knowing:

- `%NAME%` environment-variable references in a payload are still expanded.
- The command is for PowerShell only — in `cmd`, git-bash, or WSL, `curl.exe` chokes on `--%`; use the default `shell="sh"` output there. On `pwsh` 7.2+, run `$PSNativeCommandArgumentPassing = 'Legacy'` in the session first.

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

### `to_curl(request, shell="sh", pretty=False, long_options=False) -> str`

Render a request object as a `curl` command. Use for synchronous request types (`requests.PreparedRequest`, `httpx.Request`, `httpx2.Request`).

### `to_curl_async(request, shell="sh", pretty=False, long_options=False) -> str`

Async variant. Use for server-side request objects whose body must be `await`-ed (`aiohttp.web.Request`, `starlette.requests.Request`) or when you prefer the async pathway for `httpx` / `httpx2`.

`shell` selects the output dialect: `"sh"` (default, POSIX shells) or `"powershell"` (Windows PowerShell 5.1; for `pwsh` 7.2+ see the PowerShell section). `pretty` breaks the command across lines, `long_options` spells the options out; both default to `False`, which keeps the output on a single line with short options.

Both functions raise `ValueError` if the request type or the `shell` value is not recognized, if `pretty=True` is combined with `shell="powershell"`, if the body is not valid UTF-8 and `shell="powershell"` (raw bytes have no spelling behind the `--%` token), or if the body contains a NUL byte.

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
| Binary | `--data-raw $'\xff\xfe'` when the body is not valid UTF-8 |
| Cookies | `-b k=v` (lifted out of the `Cookie` header, quoted when it needs it) |
| Headers | `-H 'name: value'` (lowercased) |

`Content-Length` is dropped. If a body is present without `Content-Type`, `content-type: text/plain` is added so `curl` does not guess.

A body that does not decode as UTF-8 is rendered as an ANSI-C quoted literal, with only the bytes that have to be escaped escaped — so a mis-encoded text body stays readable as `--data-raw $'caf\xe9'`. Two things follow from that:

- `$'…'` is understood by `bash`, `zsh` and `ksh`, but it is **not** POSIX: `dash` and BusyBox `ash` pass `$\xff\xfe` through literally. The dialect is named `sh`, but a binary body needs one of the former.
- `--data-raw`, not `-d`: both `-d` and `--data-binary` read a leading `@` as a filename to load the body from, and `@` is an ordinary byte in a binary payload.

A body containing a NUL byte raises `ValueError`. A command-line argument is NUL-terminated, so no quoting can carry one — a command that ran and silently sent a truncated body would be worse than one that refuses to be rendered.

## Development

The project uses [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/).

```sh
uv sync --group dev
just tests   # pytest
just lint    # ruff format --check, ruff check, ty check
just fmt     # ruff check --fix, then ruff format
```

`just fmt` runs the linter before the formatter on purpose: a `--fix` can leave code the formatter still has to lay out.

Formatting and linting are handled by [`ruff`](https://docs.astral.sh/ruff/), type checking by [`ty`](https://docs.astral.sh/ty/).

One convention the tooling cannot enforce on its own: every parameter of a function goes on its own line, which means every parameter list ends with a trailing comma. Write the comma and the formatter keeps the layout.

CI runs the linter and the type checker on every pull request, and the test suite on Python 3.10–3.14. A separate `windows-latest` job runs the end-to-end tests against the real `powershell.exe` 5.1 and `pwsh`, so the PowerShell dialect is verified by the shell it targets rather than by string comparison alone. The POSIX end-to-end tests do the same through `bash`: the generated command is executed and a local server checks the request arrived byte-for-byte.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE).
