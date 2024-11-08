import httpx

from curlify3._base import AsyncBaseRequestData, BaseRequestData


class HttpxRequest(BaseRequestData):
    _instance_of = httpx.Request

    def body(self):
        data = self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data


class AsyncHttpxRequest(AsyncBaseRequestData):
    _instance_of = httpx.Request

    async def body(self):
        data = await self._request.aread()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
