import httpx2

from curlify3._base import AsyncBaseRequestData, BaseRequestData
from curlify3._types import Body


class Httpx2Request(BaseRequestData[httpx2.Request]):
    _instance_of = httpx2.Request
    # renders as curl --http2
    http2 = True

    def body(
        self,
    ) -> Body:
        data = self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data


class AsyncHttpx2Request(AsyncBaseRequestData[httpx2.Request]):
    _instance_of = httpx2.Request
    http2 = True

    async def body(
        self,
    ) -> Body:
        data = await self._request.aread()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
