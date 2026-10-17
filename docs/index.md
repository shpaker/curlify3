# curlify3

Convert request objects from popular Python HTTP libraries into ready-to-run `curl` commands.

`curlify3` takes a request object — one your code is about to send, or one your server has just received — and renders it as the `curl` command that sends the same request. Use it to log requests in a form you can replay, to attach reproductions to bug reports, or to see what a client actually put on the wire.

```python
import requests
from curlify3 import to_curl

req = requests.Request("POST", "https://httpbin.org/post", json={"date": "2026-08-10"}).prepare()
print(to_curl(req))
# curl -X POST -H 'content-type: application/json' -d '{"date": "2026-08-10"}' https://httpbin.org/post
```

## Features

- Two entrypoints for every library: {py:func}`~curlify3.to_curl` (sync) and {py:func}`~curlify3.to_curl_async` (async), dispatching on the type of the request object.
- **Client-side** requests from `requests`, `niquests`, `httpx`, `httpx2`, `aiohttp`, `tornado` and the stdlib's `urllib.request`; **server-side** requests from `starlette` / `fastapi`, `aiohttp.web`, `django`, `flask` / `werkzeug` and `tornado`.
- Headers, cookies, query strings and bodies — text, JSON, forms, multipart, binary — rendered so the command sends what the request carried.
- Every value quoted for the target shell, so a command rendered from an untrusted request is safe to paste.
- POSIX shell output by default, Windows PowerShell output with `shell="powershell"`.
- One line by default, one option per line with `pretty=True`, long option names with `long_options=True`.
- Per-call header filtering (`include_headers`, `exclude_headers`) and masking (`mask_headers`), so commands can go to logs.
- A [pytest plugin](integrations/pytest.md) that attaches the commands a failing test sent to its report, and a [Robot Framework library](integrations/robot.md).
- Zero runtime dependencies; fully annotated and `py.typed`.

## Installation

```console
$ pip install curlify3
```

Python 3.10 or newer. The libraries `curlify3` renders requests of are not dependencies: an adapter is active when its library is importable. The Robot Framework library needs the `robot` extra, `pip install curlify3[robot]`.

```{toctree}
:caption: Guide
:maxdepth: 2

guide/rendering
guide/headers
guide/logging
guide/powershell
```

```{toctree}
:caption: Reference
:maxdepth: 2

adapters
payloads
security
api
```

```{toctree}
:caption: Integrations
:maxdepth: 2

integrations/pytest
integrations/robot
```

```{toctree}
:caption: Project
:maxdepth: 1

comparison
development
changelog
```
