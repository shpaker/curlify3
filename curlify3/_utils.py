from contextlib import suppress

_REQUEST_DATA_CLASSES = []
_REQUEST_DATA_CLASSES_ASYNC = []


with suppress(ImportError):
    from curlify3._req_requests import RequestsRequest

    _REQUEST_DATA_CLASSES.append(RequestsRequest)


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


def _find_request_data_obj(request, request_data_classes):
    obj = None
    for _cls in request_data_classes:
        try:
            obj = _cls(request)
        except ValueError:
            continue
    if obj is None:
        raise ValueError('unknown request object')
    return obj


def make_request_obj(request):
    return _find_request_data_obj(request, _REQUEST_DATA_CLASSES)


def make_request_obj_async(request):
    if data_obj := _find_request_data_obj(request, _REQUEST_DATA_CLASSES_ASYNC):
        return data_obj
    return _find_request_data_obj(request, _REQUEST_DATA_CLASSES)
