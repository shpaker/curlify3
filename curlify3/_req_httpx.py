"""Adapters for httpx.Request, sync and async.

    import httpx
    from curlify3 import to_curl

    req = httpx.Request("POST", "https://httpbin.org/post", json={"hello": "world"})
    print(to_curl(req))

The async entrypoint takes the same object, from async code:

    print(await to_curl_async(req))
"""

import httpx

from curlify3._base import AsyncBaseRequestData, BaseRequestData
from curlify3._types import Body


class HttpxRequest(BaseRequestData[httpx.Request]):
    _instance_of = httpx.Request

    def body(
        self,
    ) -> Body:
        data = self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data


class AsyncHttpxRequest(AsyncBaseRequestData[httpx.Request]):
    _instance_of = httpx.Request

    async def body(
        self,
    ) -> Body:
        data = await self._request.aread()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
