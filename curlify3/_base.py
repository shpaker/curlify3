from abc import ABC, abstractmethod
from typing import Dict, Any

from curlify3._errors import UnknownRequestObject


class BaseRequestData(ABC):
    _instance_of: type

    def __init__(
        self,
        request,
    ) -> None:
        if not isinstance(request, self._instance_of):
            raise UnknownRequestObject
        self._request = request

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
        if self._request.headers.get('cookie'):
            del headers['cookie']
        return headers

    @property
    def cookies(self) -> str | None:
        if 'cookie' not in self._request.headers:
            return None
        return self._request.headers.get('cookie')

    @abstractmethod
    def body(
        self,
    ) -> str:
        raise NotImplementedError


class AsyncBaseRequestData(BaseRequestData, ABC):
    @abstractmethod
    async def body(
        self,
    ) -> str:
        raise NotImplementedError
