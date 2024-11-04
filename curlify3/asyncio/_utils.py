from contextlib import suppress

from curlify3._curl import make_curl_string
from curlify3._utils import make_request_data_obj

_REQUEST_DATA_CLASSES = []

with suppress(ImportError):
    from curlify3.libraries._httpx import AsyncHttpxRequest

    _REQUEST_DATA_CLASSES.append(AsyncHttpxRequest)


async def to_curl(request):
    data = make_request_data_obj(request, _REQUEST_DATA_CLASSES)
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=await data.body(),
        cookies=data.cookies,
    )
