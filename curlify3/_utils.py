from contextlib import suppress

from curlify3._curl import make_curl_string

_REQUEST_DATA_CLASSES = []


with suppress(ImportError):
    from curlify3.libraries._requests import RequestsRequest

    _REQUEST_DATA_CLASSES.append(RequestsRequest)


with suppress(ImportError):
    from curlify3.libraries._httpx import HttpxRequest

    _REQUEST_DATA_CLASSES.append(HttpxRequest)


def make_request_data_obj(request, request_data_classes):
    obj = None
    for _cls in request_data_classes:
        try:
            obj = _cls(request)
        except ValueError:
            continue
    if obj is None:
        raise ValueError
    return obj


def to_curl(request):
    data = make_request_data_obj(request, _REQUEST_DATA_CLASSES)
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=data.body(),
        cookies=data.cookies,
    )
