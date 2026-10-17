# curlify3

[![PyPI](https://img.shields.io/pypi/v/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Downloads](https://img.shields.io/pypi/dm/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Python](https://img.shields.io/pypi/pyversions/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![Tests](https://github.com/shpaker/curlify3/actions/workflows/tests.yml/badge.svg)](https://github.com/shpaker/curlify3/actions/workflows/tests.yml)
[![Docs](https://img.shields.io/badge/docs-shpaker.github.io%2Fcurlify3-blue)](https://shpaker.github.io/curlify3/)

Convert request objects from popular Python HTTP libraries into ready-to-run `curl` commands.

```sh
pip install curlify3
```

```python
import requests
from curlify3 import to_curl

req = requests.Request("POST", "https://httpbin.org/post", json={"date": "2026-08-10"}).prepare()
print(to_curl(req))
# curl -X POST -H 'content-type: application/json' -d '{"date": "2026-08-10"}' https://httpbin.org/post
```

Incoming requests work the same way — log every request as a command you can replay:

```python
from curlify3 import SENSITIVE_HEADERS, to_curl_async

@app.middleware("http")
async def log_request_as_curl(request, call_next):
    logger.info(await to_curl_async(request, mask_headers=SENSITIVE_HEADERS))
    return await call_next(request)
```

## Features

- `to_curl()` and `to_curl_async()` for `requests`, `niquests`, `httpx`, `httpx2`, `aiohttp`, `tornado`, `urllib.request`, and server-side `starlette` / `fastapi`, `aiohttp.web`, `django`, `flask` / `werkzeug`, `tornado`
- Every value quoted for the shell, so commands rendered from untrusted requests are safe to paste
- POSIX shell or Windows PowerShell output, one-line or pretty
- Per-call header filtering and secret masking
- A pytest plugin that attaches the commands of a failing test to its report, and a Robot Framework library
- Zero runtime dependencies, fully typed

## Documentation

**[shpaker.github.io/curlify3](https://shpaker.github.io/curlify3/)** — guides, supported request objects, payload handling, API reference.

[Changelog](https://github.com/shpaker/curlify3/blob/main/CHANGELOG.md) · [Contributing](https://github.com/shpaker/curlify3/blob/main/CONTRIBUTING.md) · [Security](https://github.com/shpaker/curlify3/blob/main/SECURITY.md) · [MIT License](https://github.com/shpaker/curlify3/blob/main/LICENSE)
