from typing import Any, Optional, Union

import httpx

from curlify3._base import BaseRequestData, AsyncBaseRequestData


class HttpxRequest(
    BaseRequestData,
):
    _instance_of = httpx.Request

    @property
    def url(self) -> str:
        return str(self._request.url)

    @property
    def method(
        self,
    ) -> str:
        return self._request.method

    @property
    def headers(
        self,
    ) -> dict[str, Any]:
        headers = dict(self._request.headers)
        if self._request.headers.get('cookie'):
            del headers['cookie']
        return headers

    @property
    def cookies(self) -> str | None:
        if 'cookie' not in self._request.headers:
            return None
        return self._request.headers.get('cookie')

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
