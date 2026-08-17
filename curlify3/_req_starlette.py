from starlette.requests import Request

from curlify3._base import AsyncBaseRequestData
from curlify3._types import Body


class StarletteRequest(AsyncBaseRequestData[Request]):
    _instance_of = Request

    async def body(self) -> Body:
        data = await self._request.body()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
