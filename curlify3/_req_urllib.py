"""Adapter for urllib.request.Request — stdlib, no third-party client required.

A request without an explicit method renders the one urllib would send: POST
when it carries data, GET otherwise.

    import urllib.request
    from curlify3 import to_curl

    req = urllib.request.Request(
        "https://httpbin.org/post",
        data=b'{"hello": "world"}',
        headers={"Content-Type": "application/json"},
    )

    print(to_curl(req))
    # curl -X POST -H 'content-type: application/json' -d '{"hello": "world"}' https://httpbin.org/post
"""

from collections.abc import Iterable
from typing import Any
from urllib.request import Request

from curlify3._base import BaseRequestData
from curlify3._types import Body, Headers


# Request falls outside the RawRequest protocol — there is no url attribute
# (full_url instead) and method may be unset — so the type parameter stays Any
# and every accessor is overridden
class UrllibRequest(BaseRequestData[Any]):
    _instance_of = Request

    @property
    def url(
        self,
    ) -> str:
        return self._request.full_url

    @property
    def method(
        self,
    ) -> str:
        # method is optional on the object; when absent, urllib infers POST for
        # a request carrying data and GET otherwise, and the command must match
        return self._request.get_method()

    def _header_items(
        self,
    ) -> Iterable[tuple[Any, Any]]:
        # headers live in a plain case-sensitive dict under capitalize()d keys,
        # with the unredirected ones kept apart; header_items() merges both
        return self._request.header_items()

    @property
    def headers(
        self,
    ) -> Headers:
        headers = super().headers
        # urllib adds this one when the request is sent, if it carries data and no
        # content-type of its own; without it the command would claim text/plain
        if self._request.data is not None:
            headers.setdefault("content-type", "application/x-www-form-urlencoded")
        return headers

    def body(
        self,
    ) -> Body:
        data = self._request.data
        if isinstance(data, bytes):
            try:
                return data.decode()
            except UnicodeDecodeError:
                return data
        if data is None or isinstance(data, str):
            return data
        # urllib also accepts an iterable or a file-like object as data. A
        # streaming payload has no textual form a shell could run, so the
        # command carries no -d (matching the requests adapter)
        return None
