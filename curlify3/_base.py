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
    @abstractmethod
    def url(
        self,
    ) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def cookies(
        self,
    ) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def method(
        self,
    ) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def headers(
        self,
    ) -> Dict[str, Any]:
        raise NotImplementedError

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
