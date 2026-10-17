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
- Header filtering per call: `exclude_headers` drops the noise, `include_headers` keeps only what matters
- Secret masking per call: `mask_headers` keeps a header but masks its value, so commands can go to logs
- A pytest plugin that attaches the curl commands of the requests a failing test sent to its report
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
print(to_curl(response.request, pretty=True))
# curl https://httpbin.org/get \
#   -H 'user-agent: python-requests/2.34.2' \
#   -H 'accept-encoding: gzip, deflate' \
#   -H 'accept: */*' \
#   -H 'connection: keep-alive'
```

## Usage

Every supported request object goes through the same two calls — `to_curl(request)` when the body is already in memory, `to_curl_async(request)` when it has to be `await`-ed. [Supported request objects](#supported-request-objects) lists which call fits which type, and the docstring of each adapter module (`curlify3/_req_*.py`) carries a usage example for its library.

### Logging middleware (`fastapi`)

On the server side, the same call turns into a one-function logging middleware that records every incoming request as a command ready to be replayed:

```python
import logging

from fastapi import FastAPI, Request
from curlify3 import SENSITIVE_HEADERS, to_curl_async

logger = logging.getLogger("app.requests")

app = FastAPI()

@app.middleware("http")
async def log_request_as_curl(request: Request, call_next):
    # Reading the body in a middleware is safe here: starlette caches what
    # to_curl_async() consumed and replays it, so the route handler still
    # receives the full body (starlette >= 0.28).
    curl = await to_curl_async(
        request,
        # drop the headers every client sends on its own, they only add noise
        exclude_headers=["accept", "accept-encoding", "connection", "user-agent"],
        # keep tokens, API keys and cookie values out of the log
        mask_headers=SENSITIVE_HEADERS,
    )
    # Log before handing over to the handler, so the command is captured
    # even for requests the handler then fails on — the ones worth replaying.
    logger.info("incoming request: %s", curl)
    return await call_next(request)
```

An authenticated `POST` with a JSON body arrives in the log as:

```
incoming request: curl -X POST -H 'host: api.example.com' -H 'authorization: Bearer ***' -H 'content-type: application/json' -d '{"item":"book","qty":2}' http://api.example.com/orders
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

### Filtering headers

`exclude_headers` leaves the named headers out of the command, `include_headers` renders only the named ones. Names match case-insensitively. Handy for logs, where the headers a client adds on its own drown out the ones the request is about:

```python
import requests
from curlify3 import to_curl

req = requests.Session().prepare_request(requests.Request(
    "POST",
    "https://httpbin.org/post",
    headers={"Authorization": "Bearer t0ken"},
    json={"date": "2026-08-10"},
))

print(to_curl(req, exclude_headers=["user-agent", "accept-encoding", "accept", "connection"]))
# curl -X POST -H 'authorization: Bearer t0ken' -H 'content-type: application/json' -d '{"date": "2026-08-10"}' https://httpbin.org/post

print(to_curl(req, include_headers=["content-type"]))
# curl -X POST -H 'content-type: application/json' -d '{"date": "2026-08-10"}' https://httpbin.org/post
```

The two combine: `include_headers` narrows first and `exclude_headers` subtracts from what is left. `include_headers=[]` renders no headers at all, while the default `None` renders all of them. `Cookie` counts as a header, so a filter that drops it drops `-b` as well. The filter only decides what is printed: leaving out `content-type` hides its `-H` line, but a multipart body is still rendered as `-F` parts. A bare string such as `exclude_headers="accept"` raises `TypeError`, because it would otherwise be read one character at a time.

### Masking secrets

`mask_headers` keeps the named headers in the command but prints `***` in place of their values. The command still shows what the request carried, without the credentials — paste the real value back in to replay it. `SENSITIVE_HEADERS` holds the usual suspects: `authorization`, `proxy-authorization`, `cookie`, `x-api-key`, `x-auth-token` and `x-csrf-token`.

```python
import requests
from curlify3 import SENSITIVE_HEADERS, to_curl

req = requests.Request(
    "GET",
    "https://httpbin.org/get",
    headers={"Authorization": "Bearer t0ken", "X-Api-Key": "k3y"},
    cookies={"sid": "s3cret", "theme": "dark"},
).prepare()

print(to_curl(req, mask_headers=SENSITIVE_HEADERS))
# curl -b 'sid=***; theme=***' -H 'authorization: Bearer ***' -H 'x-api-key: ***' https://httpbin.org/get
```

`authorization` and `proxy-authorization` keep their scheme (`Basic`, `Bearer`, …), and a masked `cookie` keeps the name of each cookie in `-b`. Names match case-insensitively, and the option combines with the filters: `include_headers` / `exclude_headers` decide which headers are printed, `mask_headers` then masks what is left. Masking is opt-in — the default masks nothing, so a command copied from a debugger still works as is. Only headers are covered: a secret in the query string or the body is printed as it is.

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

`curl.exe` avoids the `Invoke-WebRequest` alias, and `--%` — PowerShell's stop-parsing token — hands the rest to `curl.exe` verbatim. The token is what makes arbitrary JSON survive: without it, 5.1's argument binder re-quotes values by counting every double quote, escaped or not, and mangles the body. Three consequences worth knowing:

- `%NAME%` environment-variable references in a payload are still expanded.
- A value holding a line break — a pretty-printed JSON body, a multi-line text field — raises `ValueError`: `--%` ends at the line break, so the next line would run as a PowerShell command of its own. Use `shell="sh"` for those.
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

### pytest: curl for failing tests

The bundled pytest plugin records the HTTP requests a test sends and, when the test fails, attaches them to its report as commands to replay from a terminal. Load it from the root `conftest.py` (or pass `-p curlify3.pytest_plugin`):

```python
pytest_plugins = ["curlify3.pytest_plugin"]
```

It is not registered through a `pytest11` entry point on purpose: importing `curlify3` imports every installed library it has an adapter for, and that should not land on every pytest run in an environment that merely has `curlify3` installed.

Loading the plugin records nothing yet. Turn the capture on for the whole run with `--curl-on-failure`, or in the ini file:

```ini
[pytest]
curl_on_failure = true
```

A failing test then reports every request it sent, numbered in the order they went out, under the status of the response — or the exception the client raised:

```python
from fastapi.testclient import TestClient

def test_create_order():
    client = TestClient(app)
    client.post("/login", json={"user": "alice"})
    resp = client.post("/orders", json={"qty": 2})
    assert resp.status_code == 201
```

```
------------------------------ Captured curl call ------------------------------
# [1] 200
curl --http2 -X POST -H 'host: testserver' ... -d '{"user":"alice"}' http://testserver/login
# [2] 422
curl --http2 -X POST -H 'host: testserver' ... -d '{"qty":2}' http://testserver/orders
```

The comments are shell comments, so the section pastes as a whole. With the global switch the capture starts with the test's setup, so requests sent by its fixtures are listed too. Passing tests report nothing.

To capture a single test, request the `curl_requests` fixture instead of the global switch. It returns the commands rendered so far, which also makes them available to assertions and messages:

```python
import httpx

def test_profile(curl_requests):
    resp = httpx.get("https://api.example.com/me")
    assert resp.status_code == 200, curl_requests[-1]
```

Requests are recorded at the clients' `send`: `httpx` and `httpx2`, sync and async — which covers the starlette / FastAPI `TestClient` — `requests` and `niquests`, sync and async. One call to `send` is one entry: `requests` follows a redirect by calling `send` again, so every hop is listed, while `httpx` follows it inside `send`, so only the first request is. The body is rendered as the request is sent, before anything consumes it. A request that cannot be rendered is listed as a `# not rendered: …` comment and never fails the test.

| ini option | default | |
| --- | --- | --- |
| `curl_on_failure` | `false` | the same as `--curl-on-failure` |
| `curl_exclude_headers` | none | header names left out of the commands, one per line |
| `curl_mask_headers` | none | header names kept in the commands with `***` in place of their values, one per line, see [Masking secrets](#masking-secrets) |
| `curl_max_requests` | `20` | how many of the last requests a report lists; `0` lists all |

The commands carry the headers as sent, `Authorization` and cookies included, and test reports often end up in CI logs. Mask what should not be there:

```ini
[pytest]
curl_on_failure = true
curl_mask_headers =
    authorization
    cookie
    x-api-key
```

## API

### `to_curl(request, shell="sh", pretty=False, long_options=False, include_headers=None, exclude_headers=(), mask_headers=()) -> str`

Render a request object as a `curl` command. Use for synchronous client-side request types (`requests.PreparedRequest`, `niquests.PreparedRequest`, `httpx.Request`, `httpx2.Request`, `urllib.request.Request`, `tornado.httpclient.HTTPRequest`) and for server-side requests whose body the framework has already buffered (`django.http.HttpRequest`, `werkzeug.wrappers.Request` / `flask.Request`, `tornado.httputil.HTTPServerRequest`).

### `to_curl_async(request, shell="sh", pretty=False, long_options=False, include_headers=None, exclude_headers=(), mask_headers=()) -> str`

Async variant. Use for request objects whose body must be `await`-ed (`aiohttp.web.Request`, `aiohttp.ClientRequest`, `starlette.requests.Request`) or when you prefer the async pathway for `httpx` / `httpx2`.

`shell` selects the output dialect: `"sh"` (default, POSIX shells) or `"powershell"` (Windows PowerShell 5.1; for `pwsh` 7.2+ see the PowerShell section). `pretty` breaks the command across lines, `long_options` spells the options out; both default to `False`, which keeps the output on a single line with short options. `include_headers` / `exclude_headers` filter the rendered headers by name, see [Filtering headers](#filtering-headers). `mask_headers` masks the values of the named headers, see [Masking secrets](#masking-secrets).

Both functions raise `curlify3.UnsupportedRequestError` if no adapter accepts the request object. It subclasses both `TypeError` and `ValueError`, so `except ValueError` written against earlier releases still catches it. The message names the type that was passed, and when the other entrypoint accepts it — a starlette request handed to `to_curl()`, say — it says to use that one instead:

```
unknown request object: starlette.requests.Request, it is accepted by to_curl_async(), use that instead
```

They raise `ValueError` if the `shell` value is not recognized, if `pretty=True` is combined with `shell="powershell"`, if the body — or a multipart field value — is not valid UTF-8 and `shell="powershell"` (raw bytes have no spelling behind the `--%` token), if any value contains a line break and `shell="powershell"`, or if the body or a multipart field value contains a NUL byte. They raise `TypeError` if `include_headers`, `exclude_headers` or `mask_headers` is a `str` rather than an iterable of names, or holds a name that is not a `str`.

## Supported request objects

| Library | Type | `to_curl` | `to_curl_async` | Notes |
| --- | --- | :---: | :---: | --- |
| `requests` | `PreparedRequest` | ✅ | — | Pass `Request(...).prepare()` |
| `niquests` | `PreparedRequest` | ✅ | — | Pass `Request(...).prepare()`; HTTP/2 and HTTP/3 live on the transport, so no `--http2` |
| `httpx` | `httpx.Request` | ✅ | ✅ | |
| `httpx2` | `httpx2.Request` | ✅ | ✅ | Adds `--http2` |
| `urllib.request` | `urllib.request.Request` | ✅ | — | stdlib; an absent method and content-type are inferred the way urllib sends them |
| `aiohttp` | `aiohttp.web.Request` | — | ✅ | Server-side, body is read from the stream |
| `aiohttp` | `aiohttp.ClientRequest` | — | ✅ | Client-side, reachable in client middlewares (aiohttp 3.12+, non-consuming body read 3.12.1+) |
| `starlette` / `fastapi` | `starlette.requests.Request` | — | ✅ | Server-side, body is read from the stream; safe in middlewares, starlette replays it; the path comes from `raw_path`, still encoded |
| `django` | `django.http.HttpRequest` | ✅ | — | Server-side, body already buffered; a consumed stream renders without `-d`; the path comes from `RAW_URI` / `REQUEST_URI` when the server sets them; a host outside `ALLOWED_HOSTS` is rendered rather than raised |
| `flask` / `werkzeug` | `werkzeug.wrappers.Request` | ✅ | — | Server-side; covers Flask through its Werkzeug base; the path comes from `RAW_URI` / `REQUEST_URI` when the server sets them; a form parsed before rendering is encoded again, a parsed multipart one renders without `-d` |
| `tornado` | `tornado.httpclient.HTTPRequest` | ✅ | — | Client-side; renders the headers the client derives from `auth_username`, `user_agent` and `decompress_response` |
| `tornado` | `tornado.httputil.HTTPServerRequest` | ✅ | — | Server-side, body already read |

## Payload handling

| Payload | Rendered as |
| --- | --- |
| Plain text | `-d 'text'` |
| JSON | `-d '{"k":"v"}'` with `content-type: application/json` |
| Form-encoded | `-d 'k=v&k2=v2'` with `content-type: application/x-www-form-urlencoded` |
| Multipart / files | `-F 'field=@file' -F 'other=value'`, in the order the body carries the parts; the `boundary` parameter is left out of `-H 'content-type: …'`, since `-F` brings its own |
| Empty file input | `-F 'field=;filename=""'` for a part with `filename=""` |
| Other multipart | `multipart/related`, `multipart/mixed` and the rest go out as the body they are, with their own boundary |
| Binary | `--data-raw $'\xff\xfe'` when the body is not valid UTF-8 |
| File reference | `--data-raw '@name'` / `--form-string 'field=@name'` when a value starts with `@` or `<` |
| Field `-F` would parse | `--form-string 'field=x;type=y'` when a value holds a `;` or starts with `"` |
| Filename `-F` would split | `-F 'f=@"a;b.txt"'` when a filename holds `;`, `,`, `"` or `\` |
| Cookies | `-b k=v` (lifted out of the `Cookie` header, quoted when it needs it; repeated `Cookie` headers joined with `; `); `-H 'cookie: …'` when the value has no `=` |
| Headers | `-H 'name: value'` (lowercased; a repeated header joined with `, `, an empty one as `-H 'name;'`) |
| Url with `[]` or `{}` | `-g`, so `curl` does not expand them as a glob |

`Content-Length` is dropped. If a body is present without `Content-Type`, `content-type: text/plain` is added so `curl` does not guess — except where the client itself sends `application/x-www-form-urlencoded` (`urllib.request`, and `tornado` for a POST), which is what the command carries then.

The method follows what `curl` would send otherwise: a GET that carries a body is spelled `-X GET`, since a body alone makes `curl` send POST, and a HEAD is spelled `-I`, since `-X HEAD` leaves `curl` waiting for a response body that never comes.

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

The same goes for the rest of what `curl` parses in those values. In a `-F` value a `;` starts an attribute — `;headers=@file` loads the part headers from a local file, `;type=` and `;filename=` change the part — and a leading `"` opens a quoted string, so such a value goes through `--form-string` as well. A filename that holds `;`, `,`, `"` or `\` is written as a quoted string, `-F 'f=@"a;b.txt"'`, which `curl` does not cut short. And `-b` reads a value without an `=` as the name of a cookie file, so a `Cookie` header that holds no `name=value` pair is rendered with `-H` instead.

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

CI runs the linter and the type checker on every pull request, and the test suite on Python 3.10–3.15. A separate `windows-latest` job runs the end-to-end tests against the real `powershell.exe` 5.1 and `pwsh`, so the PowerShell dialect is verified by the shell it targets rather than by string comparison alone. The POSIX end-to-end tests do the same through `bash`: the generated command is executed and a local server checks the request arrived byte-for-byte.

## Versioning

From 1.0.0 on, `curlify3` follows [Semantic Versioning](https://semver.org/), with three-part versions (`MAJOR.MINOR.PATCH`); the 0.x releases were tagged with two.

The public API is:

- `to_curl()` and `to_curl_async()`, their parameters and their defaults
- the `SH`, `POWERSHELL` and `SENSITIVE_HEADERS` constants — a minor release may add names to `SENSITIVE_HEADERS`, never remove one
- `UnsupportedRequestError` and the `ValueError` / `TypeError` contract documented in [API](#api)
- the pytest plugin `curlify3.pytest_plugin`: its option, ini setting, fixture and the `Captured curl` report section
- the request types listed in [Supported request objects](#supported-request-objects)
- the rendered command

The rendered command is promised by what it sends, not by its spelling: within a major version, a command rendered for a request keeps sending that request. Its text — option order, which values are quoted and how, header order — may change in a minor release, always with a changelog entry, and never in a patch release unless the old text sent something other than the request. Pin a minor version if your tests compare the output string verbatim.

Everything else under `curlify3._*`, the adapter classes included, is internal and may change in any release.

A minor release may add parameters, request types and shell dialects, and may drop a Python version that has reached its end of life or a library version its own maintainers no longer support, noted in the changelog. Removing or renaming anything public, changing a default, or dropping a supported request type takes a major release.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE).
