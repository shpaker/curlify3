from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar, cast

from curlify3._types import Body, Headers, RawRequest

RequestT = TypeVar("RequestT", bound=RawRequest)


def _header_value(
    value: Any,  # noqa: ANN401
) -> str:
    # the wrapped header containers disagree on the value type — requests
    # declares str | bytes — and everything downstream reads header values as
    # text (`"multipart" in content_type`, `" " in cookies`)
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value if isinstance(value, str) else str(value)


class _RequestData(ABC, Generic[RequestT]):
    # the request type the adapter accepts, set by every concrete adapter
    _instance_of: ClassVar[type[Any]]
    http2: ClassVar[bool] = False

    def __init__(
        self,
        request: object,
    ) -> None:
        if not isinstance(request, self._instance_of):
            raise ValueError
        self._request = cast(RequestT, request)

    @property
    def url(
        self,
    ) -> str:
        return str(self._request.url)

    @property
    def method(
        self,
    ) -> str:
        return self._request.method

    @property
    def headers(
        self,
    ) -> Headers:
        headers = {name.lower(): _header_value(value) for name, value in dict(self._request.headers).items()}
        if self._request.headers.get("cookie"):
            del headers["cookie"]
        return headers

    @property
    def cookies(
        self,
    ) -> str | None:
        if "cookie" not in self._request.headers:
            return None
        return _header_value(self._request.headers.get("cookie"))


# the sync and async bases are siblings on purpose: an async body() cannot
# override a sync one, and the starlette adapter needs the async variant
class BaseRequestData(_RequestData[RequestT], ABC):
    @abstractmethod
    def body(
        self,
    ) -> Body:
        raise NotImplementedError


class AsyncBaseRequestData(_RequestData[RequestT], ABC):
    @abstractmethod
    async def body(
        self,
    ) -> Body:
        raise NotImplementedError
