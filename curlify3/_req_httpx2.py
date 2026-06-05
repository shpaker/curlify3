import httpx2

from curlify3._base import AsyncBaseRequestData, BaseRequestData


class Httpx2Request(BaseRequestData):
    _instance_of = httpx2.Request
    http2 = True

    def body(self):
        data = self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data


class AsyncHttpx2Request(AsyncBaseRequestData):
    _instance_of = httpx2.Request
    http2 = True

    async def body(self):
        data = await self._request.aread()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
