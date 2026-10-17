from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar, Generic, TypeVar, cast

from curlify3._types import Body, Headers, RawRequest

RequestT = TypeVar("RequestT", bound=RawRequest)


def merge_headers(
    items: Iterable[tuple[Any, Any]],
) -> tuple[Headers, str | None]:
    # names are lowercased, and a repeated header is joined the way HTTP folds it — with
    # ", " for an ordinary header and with "; " for Cookie, whose pairs a comma would run
    # together into one value. The cookies travel as -b instead, so they come out apart;
    # an empty Cookie header carries nothing worth repeating (django's RequestFactory sets
    # one on every request it builds)
    headers: Headers = {}
    cookies: list[str] = []
    for name, value in items:
        name, value = _header_value(name).lower(), _header_value(value)
        if name == "cookie":
            if value:
                cookies.append(value)
        elif name in headers:
            headers[name] = f"{headers[name]}, {value}"
        else:
            headers[name] = value
    return headers, "; ".join(cookies) or None


def raw_request_uri(
    environ: Mapping[str, Any],
) -> str | None:
    # the request target as the WSGI server received it, path still encoded. Not part of
    # PEP 3333, so only an origin-form value is trusted, and None means rebuild it. Servers
    # disagree on whether the query string is in it (werkzeug's test builder leaves it
    # out), so the path is taken from it and the query from QUERY_STRING, which every
    # server sets
    for key in ("RAW_URI", "REQUEST_URI"):
        value = environ.get(key)
        if isinstance(value, str) and value.startswith("/"):
            path = value.partition("?")[0]
            query = environ.get("QUERY_STRING")
            return f"{path}?{query}" if query else path
    return None


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

    def _header_items(
        self,
    ) -> Iterable[tuple[Any, Any]]:
        # every pair the request carries, a repeated header once per value: dict() kept only
        # the first value off starlette's and aiohttp's containers, and httpx joins a
        # repeated header in items() — cookies included, with the wrong separator — but
        # keeps the pairs apart in multi_items()
        headers = self._request.headers
        multi_items = getattr(headers, "multi_items", None)
        return multi_items() if callable(multi_items) else headers.items()

    @property
    def headers(
        self,
    ) -> Headers:
        return merge_headers(self._header_items())[0]

    @property
    def cookies(
        self,
    ) -> str | None:
        return merge_headers(self._header_items())[1]


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
