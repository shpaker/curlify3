from typing import Any, Optional, Union

import httpx

from curlify3._base import BaseRequestData, AsyncBaseRequestData


class HttpxRequest(
    BaseRequestData,
):
    _instance_of = httpx.Request

    def body(
        self,
    ) -> Optional[Union[bytes, str]]:
        data = self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data


class AsyncHttpxRequest(
    AsyncBaseRequestData,
    HttpxRequest,
):
    async def body(
        self,
    ) -> Optional[Union[bytes, str]]:
        data = await self._request.aread()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
