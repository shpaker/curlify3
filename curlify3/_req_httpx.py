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
