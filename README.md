# curlify3

[![PyPI](https://img.shields.io/pypi/v/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Downloads](https://img.shields.io/pypi/dm/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Python](https://img.shields.io/pypi/pyversions/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Tests](https://github.com/shpaker/curlify3/actions/workflows/tests.yml/badge.svg)](https://github.com/shpaker/curlify3/actions/workflows/tests.yml)

Convert request objects from popular Python HTTP libraries into ready-to-run `curl` commands.

`curlify3` takes a request object from any supported client or server framework and renders it as an equivalent `curl` command — useful for logging, debugging, sharing reproductions, and copy-pasting from your IDE into a terminal.

## Features

- One entrypoint for everything — `to_curl()` (sync) and `to_curl_async()` (async), dispatching on the type of the request object
- Works with **client-side** requests (`requests`, `niquests`, `httpx`, `httpx2`, `aiohttp`, `tornado`, stdlib `urllib.request`) and **server-side** incoming requests (`starlette` / `fastapi`, `aiohttp.web`, `django`, `flask` / `werkzeug`, `tornado`)
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

Every supported request object goes through the same two calls — `to_curl(request)` when the body is already in memory, `to_curl_async(request)` when it has to be `await`-ed. [Supported request objects](#supported-request-objects) lists which call fits which type, and the docstring of each adapter module (`curlify3/_req_*.py`) carries a usage example for its library.

### Logging middleware (`fastapi`)

On the server side, the same call turns into a one-function logging middleware that records every incoming request as a command ready to be replayed:

```python
import logging

from fastapi import FastAPI, Request
from curlify3 import to_curl_async

logger = logging.getLogger("app.requests")

app = FastAPI()

@app.middleware("http")
async def log_request_as_curl(request: Request, call_next):
    # Reading the body in a middleware is safe here: starlette caches what
    # to_curl_async() consumed and replays it, so the route handler still
    # receives the full body (starlette >= 0.28).
    curl = await to_curl_async(request)
    # Log before handing over to the handler, so the command is captured
    # even for requests the handler then fails on — the ones worth replaying.
    logger.info("incoming request: %s", curl)
    return await call_next(request)
```

A `POST` with a JSON body arrives in the log as:

```
incoming request: curl -X POST -H 'host: api.example.com' -H 'accept: */*' -H 'content-type: application/json' -d '{"item":"book","qty":2}' http://api.example.com/orders
```

Every value in that command was chosen by the client; [Quoting and untrusted values](#quoting-and-untrusted-values) is what makes it safe to paste anyway.

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

### Quoting and untrusted values

Every rendered value is quoted for the target shell, so a body, header, cookie or url is data and never becomes part of the command. This matters most for the server-side adapters, where all of those arrive from the client:

```python
# an incoming request whose path and cookie were chosen by the caller
print(await to_curl_async(request))
# curl -b 'n=O'\''Brien' -H 'host: example.com' 'http://example.com/x;id'
```

The url and the cookie header are left bare when every character in them is safe, which is the common case and keeps the command short. Anything else is quoted — including the `?` of a single-parameter query string, which `zsh` would otherwise reject as an unmatched glob.

## API

### `to_curl(request, shell="sh", pretty=False, long_options=False) -> str`

Render a request object as a `curl` command. Use for synchronous client-side request types (`requests.PreparedRequest`, `niquests.PreparedRequest`, `httpx.Request`, `httpx2.Request`, `urllib.request.Request`, `tornado.httpclient.HTTPRequest`) and for server-side requests whose body the framework has already buffered (`django.http.HttpRequest`, `werkzeug.wrappers.Request` / `flask.Request`, `tornado.httputil.HTTPServerRequest`).

### `to_curl_async(request, shell="sh", pretty=False, long_options=False) -> str`

Async variant. Use for request objects whose body must be `await`-ed (`aiohttp.web.Request`, `aiohttp.ClientRequest`, `starlette.requests.Request`) or when you prefer the async pathway for `httpx` / `httpx2`.

`shell` selects the output dialect: `"sh"` (default, POSIX shells) or `"powershell"` (Windows PowerShell 5.1; for `pwsh` 7.2+ see the PowerShell section). `pretty` breaks the command across lines, `long_options` spells the options out; both default to `False`, which keeps the output on a single line with short options.

Both functions raise `ValueError` if the request type or the `shell` value is not recognized, if `pretty=True` is combined with `shell="powershell"`, if the body — or a multipart field value — is not valid UTF-8 and `shell="powershell"` (raw bytes have no spelling behind the `--%` token), or if either contains a NUL byte.

## Supported request objects

| Library | Type | `to_curl` | `to_curl_async` | Notes |
| --- | --- | :---: | :---: | --- |
| `requests` | `PreparedRequest` | ✅ | — | Pass `Request(...).prepare()` |
| `niquests` | `PreparedRequest` | ✅ | — | Pass `Request(...).prepare()`; HTTP/2 and HTTP/3 live on the transport, so no `--http2` |
| `httpx` | `httpx.Request` | ✅ | ✅ | |
| `httpx2` | `httpx2.Request` | ✅ | ✅ | Adds `--http2` |
| `urllib.request` | `urllib.request.Request` | ✅ | — | stdlib; an absent method is inferred the way urllib sends it |
| `aiohttp` | `aiohttp.web.Request` | — | ✅ | Server-side, body is read from the stream |
| `aiohttp` | `aiohttp.ClientRequest` | — | ✅ | Client-side, reachable in client middlewares (aiohttp 3.12+, non-consuming body read 3.12.1+) |
| `starlette` / `fastapi` | `starlette.requests.Request` | — | ✅ | Server-side, body is read from the stream; safe in middlewares, starlette replays it |
| `django` | `django.http.HttpRequest` | ✅ | — | Server-side, body already buffered; a consumed stream renders without `-d` |
| `flask` / `werkzeug` | `werkzeug.wrappers.Request` | ✅ | — | Server-side; covers Flask through its Werkzeug base |
| `tornado` | `tornado.httpclient.HTTPRequest` | ✅ | — | Client-side |
| `tornado` | `tornado.httputil.HTTPServerRequest` | ✅ | — | Server-side, body already read |

## Payload handling

| Payload | Rendered as |
| --- | --- |
| Plain text | `-d 'text'` |
| JSON | `-d '{"k":"v"}'` with `content-type: application/json` |
| Form-encoded | `-d 'k=v&k2=v2'` with `content-type: application/x-www-form-urlencoded` |
| Multipart / files | `-F 'field=@file' -F 'other=value'`, in the order the body carries the parts |
| Binary | `--data-raw $'\xff\xfe'` when the body is not valid UTF-8 |
| File reference | `--data-raw '@name'` / `--form-string 'field=@name'` when a value starts with `@` or `<` |
| Cookies | `-b k=v` (lifted out of the `Cookie` header, quoted when it needs it) |
| Headers | `-H 'name: value'` (lowercased) |

`Content-Length` is dropped. If a body is present without `Content-Type`, `content-type: text/plain` is added so `curl` does not guess.

A body that does not decode as UTF-8 is rendered as an ANSI-C quoted literal, with only the bytes that have to be escaped escaped — so a mis-encoded text body stays readable as `--data-raw $'caf\xe9'`. Two things follow from that:

- `$'…'` is understood by `bash`, `zsh` and `ksh`, but it is **not** POSIX: `dash` and BusyBox `ash` pass `$\xff\xfe` through literally. The dialect is named `sh`, but a binary body needs one of the former.
- `--data-raw`, not `-d`: both `-d` and `--data-binary` read a leading `@` as a filename to load the body from, and `@` is an ordinary byte in a binary payload.

A body containing a NUL byte raises `ValueError`. A command-line argument is NUL-terminated, so no quoting can carry one — a command that ran and silently sent a truncated body would be worse than one that refuses to be rendered. The same applies to a multipart field value, which reaches the command line the same way.

`curl` reads a leading `@` in a `--data` value, and a leading `@` or `<` in a `--form` value, as *the name of a local file to send the contents of* rather than as the value itself. A request whose body or form field genuinely starts with one of those characters is therefore rendered with the option that takes the value literally — `--data-raw` and `--form-string` — so the command sends what the request carried:

```python
print(to_curl(httpx.Request("POST", "https://example.com/", content="@/etc/passwd")))
# curl -X POST -H 'host: example.com' -H 'content-type: text/plain' \
#      --data-raw '@/etc/passwd' https://example.com/
```

This matters most on the server side, where the value is chosen by whoever sent the request: with `-d`, a command rendered into a log and later pasted into a terminal would read a local file of the caller's choosing and send it to the caller's own url. File *parts* keep `-F 'field=@file'`, where the `@` is the intended meaning.

## Comparison with `curlify` and `curlify2`

| | [`curlify`](https://pypi.org/project/curlify/) | [`curlify2`](https://pypi.org/project/curlify2/) | **`curlify3`** |
| --- | :---: | :---: | :---: |
| `requests` | ✅ | ✅ | ✅ |
| `httpx` | ❌ | ✅ | ✅ |
| `httpx2` (HTTP/2) | ❌ | ❌ | ✅ |
| `niquests` | ❌ | ❌ | ✅ |
| `urllib.request` (stdlib) | ❌ | ❌ | ✅ |
| `aiohttp` (client and server) | ❌ | ❌ | ✅ |
| `tornado` (client and server) | ❌ | ❌ | ✅ |
| `starlette` / `fastapi` (server-side) | ❌ | ❌ | ✅ |
| `django` (server-side) | ❌ | ❌ | ✅ |
| `flask` / `werkzeug` (server-side) | ❌ | ❌ | ✅ |
| Async API | ❌ | ❌ | ✅ |
| Python | 3.7+ | 3.7–3.11 | 3.10+ |

`curlify` is the original and covers only `requests`. `curlify2` added `httpx` but is sync-only, client-side-only, and has not seen a release since 2023. `curlify3` extends the same idea across the ecosystem: HTTP/2 (`httpx2`), an async entrypoint, the rest of the popular clients down to the stdlib's `urllib.request`, and server-side adapters for `aiohttp`, `starlette` / `fastapi`, `django`, `flask` / `werkzeug` and `tornado` so you can dump incoming requests as `curl` from inside a handler.

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
