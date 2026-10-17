"""Adapter for starlette.requests.Request, which covers FastAPI.

Async, the body is read from the stream:

    from fastapi import FastAPI, Request
    from curlify3 import to_curl_async

    app = FastAPI()

    @app.post("/echo")
    async def echo(request: Request):
        return {"curl": await to_curl_async(request)}

Safe in a middleware as well: starlette caches the body the render consumed and
replays it to the route handler (starlette >= 0.28) — see the logging recipes in
the documentation.
"""

from starlette.requests import Request

from curlify3._base import AsyncBaseRequestData
from curlify3._types import Body


class StarletteRequest(AsyncBaseRequestData[Request]):
    _instance_of = Request

    @property
    def url(
        self,
    ) -> str:
        # request.url is built from the percent-decoded path, which curl either rejects (a
        # space) or sends to another route (%2F, %3F and %23 come back as /, ? and #, and
        # the url is parsed again with them in it). The server keeps the path as it arrived
        # in raw_path, so the url is put together from the scope instead
        scope = self._request.scope
        raw_path = scope.get("raw_path")
        if not raw_path:
            return str(self._request.url)
        target = raw_path.decode("latin-1").partition("?")[0]
        if query := scope.get("query_string"):
            target = f"{target}?{query.decode('latin-1')}"
        # scheme and host are unaffected by the path, which follows the authority
        url = self._request.url
        return f"{url.scheme}://{url.netloc}{target}" if url.netloc else target

    async def body(
        self,
    ) -> Body:
        data = await self._request.body()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
