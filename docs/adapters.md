# Supported request objects

An adapter registers only when its library is importable, so `curlify3` itself has no runtime dependencies. The first adapter that accepts the object renders it; an object no adapter accepts raises {py:class}`~curlify3.UnsupportedRequestError`.

| Library | Type | `to_curl` | `to_curl_async` | Side |
| --- | --- | :---: | :---: | --- |
| `requests` | `requests.PreparedRequest` | ✅ | — | client |
| `niquests` | `niquests.PreparedRequest` | ✅ | — | client |
| `httpx` | `httpx.Request` | ✅ | ✅ | client |
| `httpx2` | `httpx2.Request` | ✅ | ✅ | client |
| `urllib.request` | `urllib.request.Request` | ✅ | — | client |
| `aiohttp` | `aiohttp.ClientRequest` | — | ✅ | client |
| `aiohttp` | `aiohttp.web.Request` | — | ✅ | server |
| `starlette` / `fastapi` | `starlette.requests.Request` | — | ✅ | server |
| `django` | `django.http.HttpRequest` | ✅ | — | server |
| `flask` / `werkzeug` | `werkzeug.wrappers.Request` | ✅ | — | server |
| `tornado` | `tornado.httpclient.HTTPRequest` | ✅ | — | client |
| `tornado` | `tornado.httputil.HTTPServerRequest` | ✅ | — | server |

The sections below show the call for each library and what its adapter does beyond reading the request.

## Client side

### requests

```python
import requests
from curlify3 import to_curl

req = requests.Request("POST", "https://httpbin.org/post", json={"hello": "world"}).prepare()
print(to_curl(req))
```

Pass a `PreparedRequest`: `Request(...).prepare()`, `Session().prepare_request(...)`, or `response.request` for one that was sent. A plain `requests.Request` has not been encoded yet and is not accepted.

### niquests

```python
import niquests
from curlify3 import to_curl

req = niquests.Request("POST", "https://httpbin.org/post", json={"hello": "world"}).prepare()
print(to_curl(req))
# curl -X POST -H 'content-type: application/json;charset=utf-8' -d '{"hello": "world"}' https://httpbin.org/post
```

The same shape as `requests`. HTTP/2 and HTTP/3 are negotiated on the transport, so the command carries no `--http2`. The async session sends the same `PreparedRequest`, which goes through the sync `to_curl()`.

### httpx

```python
import httpx
from curlify3 import to_curl

req = httpx.Request("POST", "https://httpbin.org/post", json={"hello": "world"})
print(to_curl(req))
# curl -X POST -H 'host: httpbin.org' -H 'content-type: application/json' -d '{"hello":"world"}' https://httpbin.org/post
```

Both calls accept it; `to_curl_async()` reads a body that is an async stream. `httpx` adds the `host` header to the request object itself, so the command carries it.

### httpx2

```python
import httpx2
from curlify3 import to_curl

req = httpx2.Request("GET", "https://httpbin.org/get")
print(to_curl(req))
# curl --http2 -H 'host: httpbin.org' https://httpbin.org/get
```

As `httpx`, plus `--http2`.

### urllib.request

```python
import urllib.request
from curlify3 import to_curl

req = urllib.request.Request(
    "https://httpbin.org/post",
    data=b'{"hello": "world"}',
    headers={"Content-Type": "application/json"},
)
print(to_curl(req))
# curl -X POST -H 'content-type: application/json' -d '{"hello": "world"}' https://httpbin.org/post
```

What urllib decides at send time is rendered as it will be sent: a request without an explicit method is POST when it carries data and GET otherwise, and data sent without a content-type gets `application/x-www-form-urlencoded`. Headers are merged from the regular and the unredirected ones. An iterable body has no text to render and the command carries no `-d`.

### aiohttp client

```python
import aiohttp
from curlify3 import to_curl_async

async def log_as_curl(request: aiohttp.ClientRequest, handler):
    print(await to_curl_async(request))
    return await handler(request)

async with aiohttp.ClientSession(middlewares=(log_as_curl,)) as session:
    await session.post("https://httpbin.org/post", json={"hello": "world"})
```

The outgoing `ClientRequest` is reachable in a client middleware (aiohttp 3.12+). Rendering does not consume the payload: in-memory bodies hand back their value, files seek back, and async iterables are cached and replayed when the request is sent. That read needs aiohttp 3.12.1+; on older versions only in-memory payloads are read, and anything else renders without `-d`, because reading it would corrupt the outgoing request.

### tornado client

```python
import tornado.httpclient
from curlify3 import to_curl

req = tornado.httpclient.HTTPRequest(
    "https://httpbin.org/post",
    method="POST",
    body='{"hello": "world"}',
    headers={"Content-Type": "application/json"},
)
print(to_curl(req))
# curl -X POST -H 'content-type: application/json' -d '{"hello": "world"}' https://httpbin.org/post
```

The command includes the headers tornado's client sets from the request's attributes when it sends it: a basic `authorization` from `auth_username` / `auth_password`, `user-agent` from `user_agent`, `accept-encoding: gzip` from `decompress_response`, and a form-encoded content-type for a POST without one. Attributes left as `None` fall back to client-wide defaults the request object cannot see, and are not rendered.

## Server side

On the server, every value in the command — path, query, headers, cookies, body — was chosen by the client. [Quoting and untrusted values](security.md) describes what keeps such a command safe to paste. The url keeps the path as it arrived, percent-encoding included, whenever the server makes it available: the decoded path would turn `%2F` into another route and `%20` into a url curl rejects.

### starlette / FastAPI

```python
from fastapi import FastAPI, Request
from curlify3 import to_curl_async

app = FastAPI()

@app.post("/echo")
async def echo(request: Request):
    return {"curl": await to_curl_async(request)}
```

Async: the body is read from the stream. Safe in a middleware — starlette caches what the render consumed and replays it to the route handler (starlette 0.28+); see the [logging recipe](guide/logging.md#fastapi--starlette). The path comes from the scope's `raw_path`.

### aiohttp server

```python
from aiohttp import web
from curlify3 import to_curl_async

async def handler(request: web.Request) -> web.Response:
    print(await to_curl_async(request))
    return web.json_response({"ok": True})
```

Async: the body is read with `request.read()`, which caches it for the handler.

### django

```python
from django.http import JsonResponse
from curlify3 import to_curl

def echo(request):
    return JsonResponse({"curl": to_curl(request)})
```

Django buffers the body before the view runs, so the sync `to_curl()` is the right call, async views included. `WSGIRequest` and `ASGIRequest` are both covered.

- The path comes from `RAW_URI` / `REQUEST_URI` when the server sets them (gunicorn and uwsgi do); otherwise from the decoded `PATH_INFO`.
- A host outside `ALLOWED_HOSTS` is rendered rather than raising `DisallowedHost`, so a logger that runs before django answers 400 still gets the command.
- A stream consumed without buffering — `request.read()`, or multipart parsing — leaves nothing to render: the command carries the headers but no `-d`.

### flask / werkzeug

```python
import flask
from curlify3 import to_curl

app = flask.Flask(__name__)

@app.post("/echo")
def echo():
    return {"curl": to_curl(flask.request)}
```

`flask.Request` subclasses `werkzeug.wrappers.Request`, so Flask and plain werkzeug apps are covered alike.

- The body is read with `get_data(cache=True, parse_form_data=False)`: form parsing after the render still works.
- A form parsed before the render has drained the stream. An urlencoded one is encoded again from the parsed fields — the same fields, though not necessarily the same bytes; a multipart one also held files and renders without `-d`.
- The path comes from `RAW_URI` / `REQUEST_URI` when the server sets them (gunicorn, uwsgi and werkzeug's own server do).

### tornado server

```python
import tornado.web
from curlify3 import to_curl

class EchoHandler(tornado.web.RequestHandler):
    def post(self):
        self.write({"curl": to_curl(self.request)})
```

tornado reads the body before the handler runs, so the incoming request renders synchronously. The url comes from `full_url()`.
