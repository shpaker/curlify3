# Logging requests as curl

The most common use of `curlify3` is a log line that can be pasted into a terminal to replay the request. The recipes below log every request at the point where the framework or the client hands it over. All of them drop the headers every client sends on its own and mask the credentials — see [Filtering and masking headers](headers.md).

```python
import logging

from curlify3 import SENSITIVE_HEADERS

logger = logging.getLogger("app.requests")

# shared by the recipes below
NOISE = ["accept", "accept-encoding", "connection", "user-agent"]
```

Log before the request is handled, so the command is captured even for the requests the handler then fails on — the ones worth replaying.

## Incoming requests

### FastAPI / starlette

```python
from fastapi import FastAPI, Request
from curlify3 import to_curl_async

app = FastAPI()

@app.middleware("http")
async def log_request_as_curl(request: Request, call_next):
    curl = await to_curl_async(request, exclude_headers=NOISE, mask_headers=SENSITIVE_HEADERS)
    logger.info("incoming request: %s", curl)
    return await call_next(request)
```

Reading the body in a middleware is safe: starlette caches what `to_curl_async()` consumed and replays it, so the route handler still receives the full body (starlette 0.28+). An authenticated `POST` arrives in the log as:

```text
incoming request: curl -X POST -H 'host: api.example.com' -H 'authorization: Bearer ***' -H 'content-type: application/json' -d '{"item":"book","qty":2}' http://api.example.com/orders
```

Every value in that command was chosen by the client. [Quoting and untrusted values](../security.md) is what makes it safe to paste anyway.

### Django

```python
from curlify3 import to_curl

class CurlLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        curl = to_curl(request, exclude_headers=NOISE, mask_headers=SENSITIVE_HEADERS)
        logger.info("incoming request: %s", curl)
        return self.get_response(request)
```

Add it to `MIDDLEWARE`. Django buffers the body when it is first read, so the view can still read `request.body` and `request.POST`. The sync `to_curl()` is the right call in async views too. A request whose stream was consumed without buffering — `request.read()`, or multipart parsing before the middleware runs — renders without `-d`.

### Flask / werkzeug

```python
import flask
from curlify3 import to_curl

app = flask.Flask(__name__)

@app.before_request
def log_request_as_curl():
    curl = to_curl(flask.request, exclude_headers=NOISE, mask_headers=SENSITIVE_HEADERS)
    logger.info("incoming request: %s", curl)
```

The body is read with caching on and form parsing off, so `request.form` and `request.files` work afterwards. A form that was parsed before rendering is encoded again from its fields; a parsed multipart form renders without `-d`.

### aiohttp server

```python
from aiohttp import web
from curlify3 import to_curl_async

@web.middleware
async def log_request_as_curl(request: web.Request, handler):
    curl = await to_curl_async(request, exclude_headers=NOISE, mask_headers=SENSITIVE_HEADERS)
    logger.info("incoming request: %s", curl)
    return await handler(request)

app = web.Application(middlewares=[log_request_as_curl])
```

`request.read()` caches the body, so the handler reads it again.

### tornado

```python
import tornado.web
from curlify3 import to_curl

class LoggedHandler(tornado.web.RequestHandler):
    def prepare(self):
        curl = to_curl(self.request, exclude_headers=NOISE, mask_headers=SENSITIVE_HEADERS)
        logger.info("incoming request: %s", curl)
```

tornado reads the body before `prepare()` runs, so the incoming request renders synchronously.

## Outgoing requests

### httpx / httpx2

Event hooks see the request just before it is sent:

```python
import httpx
from curlify3 import to_curl, to_curl_async

def log_request(request: httpx.Request) -> None:
    logger.info("outgoing request: %s", to_curl(request, mask_headers=SENSITIVE_HEADERS))

client = httpx.Client(event_hooks={"request": [log_request]})

async def log_request_async(request: httpx.Request) -> None:
    logger.info("outgoing request: %s", await to_curl_async(request, mask_headers=SENSITIVE_HEADERS))

async_client = httpx.AsyncClient(event_hooks={"request": [log_request_async]})
```

`httpx2` takes the same hooks; its commands carry `--http2`.

### requests / niquests

`requests` has no hook before sending, but every response carries the request it was sent for:

```python
import requests
from curlify3 import to_curl

def log_request(response: requests.Response, *args, **kwargs) -> None:
    logger.info("request: %s", to_curl(response.request, mask_headers=SENSITIVE_HEADERS))

session = requests.Session()
session.hooks["response"].append(log_request)
```

A redirect calls the hook once per hop, each with its own request. `niquests` sessions take the same hook.

### aiohttp client

A client middleware (aiohttp 3.12+) sees the outgoing `ClientRequest`:

```python
import aiohttp
from curlify3 import to_curl_async

async def log_request(request: aiohttp.ClientRequest, handler):
    logger.info("outgoing request: %s", await to_curl_async(request, mask_headers=SENSITIVE_HEADERS))
    return await handler(request)

async with aiohttp.ClientSession(middlewares=(log_request,)) as session:
    await session.post("https://httpbin.org/post", json={"hello": "world"})
```

Rendering does not consume the payload: in-memory bodies hand back their value, files seek back, and async iterables are cached and replayed when the request is sent. That non-consuming read needs aiohttp 3.12.1+; below it, streaming bodies render without `-d`.

## In tests

The [pytest plugin](../integrations/pytest.md) records the requests a test sends and attaches the commands to the report of a failing test, without any hooks of your own. Robot Framework suites get the same from the [Robot Framework library](../integrations/robot.md).
