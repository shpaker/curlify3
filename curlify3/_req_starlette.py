"""Adapter for starlette.requests.Request, which covers FastAPI.

Async, the body is read from the stream:

    from fastapi import FastAPI, Request
    from curlify3 import to_curl_async

    app = FastAPI()

    @app.post("/echo")
    async def echo(request: Request):
        return {"curl": await to_curl_async(request)}

Safe in a middleware as well: starlette caches the body the render consumed and
replays it to the route handler (starlette >= 0.28) — see the logging-middleware
example in the README.
"""

from starlette.requests import Request

from curlify3._base import AsyncBaseRequestData
from curlify3._types import Body


class StarletteRequest(AsyncBaseRequestData[Request]):
    _instance_of = Request

    async def body(
        self,
    ) -> Body:
        data = await self._request.body()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
