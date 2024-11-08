# yet another library to convert request object to curl command

[![PyPI](https://img.shields.io/pypi/v/curlify3.svg)](https://pypi.python.org/pypi/curlify3)
[![PyPI](https://img.shields.io/pypi/dm/curlify3.svg)](https://pypi.python.org/pypi/curlify3)

### Support request's objects from:

- requests
- httpx
- aiohttp server
- starlette/fastapi

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
