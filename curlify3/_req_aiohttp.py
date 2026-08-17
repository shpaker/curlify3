from aiohttp import web

from curlify3._base import AsyncBaseRequestData
from curlify3._types import Body


class AiohttpServerRequest(AsyncBaseRequestData[web.Request]):
    _instance_of = web.Request

    async def body(
        self,
    ) -> Body:
        data = await self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
