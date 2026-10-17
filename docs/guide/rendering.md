# Rendering a request

## Sync or async

Every supported request object goes through one of two calls:

- {py:func}`~curlify3.to_curl` when the body is already in memory — the client-side request types, and the server-side ones whose framework buffers the body before your code runs (`django`, `flask` / `werkzeug`, `tornado`);
- {py:func}`~curlify3.to_curl_async` when the body has to be awaited — `starlette` / `fastapi`, `aiohttp.web.Request` and `aiohttp.ClientRequest`.

`httpx.Request` and `httpx2.Request` work with both. [Supported request objects](../adapters.md) lists which call fits which type.

```python
import httpx
from curlify3 import to_curl, to_curl_async

req = httpx.Request("POST", "https://httpbin.org/post", json={"hello": "world"})

print(to_curl(req))
# curl -X POST -H 'host: httpbin.org' -H 'content-type: application/json' -d '{"hello":"world"}' https://httpbin.org/post

print(await to_curl_async(req))  # the same command, from async code
```

Passing an object to the wrong call raises {py:class}`~curlify3.UnsupportedRequestError`, and the message says which call takes it:

```text
unknown request object: starlette.requests.Request, it is accepted by to_curl_async(), use that instead
```

A request that has already been sent is usually still reachable: `response.request` for `requests`, `niquests` and `httpx`.

## Readable output

`pretty=True` puts every option on its own line:

```python
import requests
from curlify3 import to_curl

req = requests.Request("POST", "https://httpbin.org/post", json={"date": "2026-08-10"}).prepare()

print(to_curl(req, pretty=True))
# curl https://httpbin.org/post \
#   -X POST \
#   -H 'content-type: application/json' \
#   -d '{"date": "2026-08-10"}'
```

The url moves to the first line, where `curl` reads it as well as at the end — the layout Chrome DevTools' "Copy as cURL" uses. A request with no options stays on one line.

`long_options=True` spells the options out, `--header` instead of `-H`. The two are independent:

```python
print(to_curl(req, pretty=True, long_options=True))
# curl https://httpbin.org/post \
#   --request POST \
#   --header 'content-type: application/json' \
#   --data '{"date": "2026-08-10"}'
```

`pretty=True` is not available with `shell="powershell"`, see [Windows PowerShell](powershell.md).

## What the command contains

The command carries what the request object holds, in this order: `--http2` for `httpx2`, `-g` when the url needs globbing off, the method, the cookies as `-b`, the headers as `-H`, the body, and the url last (first with `pretty=True`).

- Header names are lowercased. A repeated header is joined with `, `, repeated `Cookie` headers with `; `.
- `Content-Length` is left out: `curl` computes it from the body it sends.
- The method is left out for a GET without a body, which is what `curl` sends by default. A GET with a body is spelled `-X GET`, since a body alone makes `curl` send POST, and a HEAD is spelled `-I`.
- A body sent without a `Content-Type` gets `content-type: text/plain`, so `curl` does not add its own form-encoded one — except where the client itself sends `application/x-www-form-urlencoded`, which the command then carries.

[Payload handling](../payloads.md) covers how each kind of body is rendered, and [Supported request objects](../adapters.md) what each library adds of its own.
