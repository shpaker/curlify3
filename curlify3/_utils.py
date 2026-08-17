from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Any, TypeVar

from curlify3._types import AsyncRequestData, RequestData

# the first adapter that accepts the request wins, so the more specific one
# comes first: httpx2 before httpx, in case a future httpx2 derives its Request
# from httpx's and an httpx2 request starts matching both — the http2 adapter
# has to keep winning, otherwise the command silently loses --http2
_REQUEST_DATA_CLASSES: list[Callable[[Any], RequestData]] = []
_REQUEST_DATA_CLASSES_ASYNC: list[Callable[[Any], AsyncRequestData]] = []


with suppress(ImportError):
    from curlify3._req_requests import RequestsRequest

    _REQUEST_DATA_CLASSES.append(RequestsRequest)


with suppress(ImportError):
    from curlify3._req_httpx2 import Httpx2Request

    _REQUEST_DATA_CLASSES.append(Httpx2Request)


with suppress(ImportError):
    from curlify3._req_httpx2 import AsyncHttpx2Request

    _REQUEST_DATA_CLASSES_ASYNC.append(AsyncHttpx2Request)


with suppress(ImportError):
    from curlify3._req_httpx import HttpxRequest

    _REQUEST_DATA_CLASSES.append(HttpxRequest)


with suppress(ImportError):
    from curlify3._req_httpx import AsyncHttpxRequest

    _REQUEST_DATA_CLASSES_ASYNC.append(AsyncHttpxRequest)


with suppress(ImportError):
    from curlify3._req_aiohttp import AiohttpServerRequest

    _REQUEST_DATA_CLASSES_ASYNC.append(AiohttpServerRequest)


with suppress(ImportError):
    from curlify3._req_starlette import StarletteRequest

    _REQUEST_DATA_CLASSES_ASYNC.append(StarletteRequest)


_DataT = TypeVar("_DataT")


def _find_request_data_obj(request: object, request_data_classes: Sequence[Callable[[Any], _DataT]]) -> _DataT:
    for _cls in request_data_classes:
        try:
            return _cls(request)
        except ValueError:
            continue
    raise ValueError('unknown request object')


def make_request_obj(request: object) -> RequestData:
    return _find_request_data_obj(request, _REQUEST_DATA_CLASSES)


def make_request_obj_async(request: object) -> AsyncRequestData:
    return _find_request_data_obj(request, _REQUEST_DATA_CLASSES_ASYNC)
