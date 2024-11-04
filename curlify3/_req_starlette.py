from typing import Optional, Union

import starlette

from starlette.requests import Request

from curlify3._base import BaseRequestData


class StarletteRequest(BaseRequestData):
    _instance_of = starlette.requests.Request

    async def body(self) -> Optional[Union[bytes, str]]:
        self._request: starlette.requests.Request
        data = await self._request.body()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
