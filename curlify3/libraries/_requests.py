from typing import Any, Optional, Union

import requests

from curlify3._base import BaseRequestData


class RequestsRequest(
    BaseRequestData,
):
    _instance_of = requests.PreparedRequest

    @property
    def cookies(self) -> str:
        return self._request.headers.get('cookie')

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
        headers = {name.lower(): value for name, value in dict(self._request.headers).items()}
        if headers.get('cookie'):
            del headers['cookie']
        return headers

    def body(
        self,
    ) -> Optional[Union[bytes, str]]:
        body = self._request.body
        if isinstance(body, bytes):
            try:
               return body.decode()
            except UnicodeDecodeError:
                pass
        return body
