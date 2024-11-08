from aiohttp import web

from curlify3._base import AsyncBaseRequestData


class AiohttpServerRequest(AsyncBaseRequestData):
    _instance_of = web.Request

    async def body(self):
        data = await self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
