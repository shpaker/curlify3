# yet another library to convert request object to curl command

[![PyPI](https://img.shields.io/pypi/v/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![PyPI](https://img.shields.io/pypi/dm/curlify3.svg)](https://pypi.python.org/pypi/curlify3)

### Support request's objects from:

- requests
- httpx
- [httpx2](https://github.com/pydantic/httpx2) (adds `--http2` to the curl)
- aiohttp server
- starlette/fastapi

Requires Python 3.10+.

## Installation

```sh
pip install curlify3
```

## Example

```py
from curlify3 import to_curl
import requests

response = requests.get("http://google.ru")
print(to_curl(response.request))
# curl -H 'user-agent: python-requests/2.32.3' -H 'accept-encoding: gzip, deflate' -H 'accept: */*' -H 'connection: keep-alive' http://www.google.ru/
```

### httpx2 (HTTP/2)

```py
import httpx2
from curlify3 import to_curl

req = httpx2.Request("GET", "https://httpbin.org/get")
print(to_curl(req))
# curl --http2 -H 'host: httpbin.org' https://httpbin.org/get
```

### async

```py
import asyncio, httpx
from curlify3 import to_curl_async

req = httpx.Request("POST", "https://httpbin.org/post", json={"a": 1})
print(asyncio.run(to_curl_async(req)))
```
