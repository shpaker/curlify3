from typing import Any
from urllib.request import Request

from curlify3._base import BaseRequestData, _header_value
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

    @property
    def headers(
        self,
    ) -> Headers:
        # headers live in a plain case-sensitive dict under capitalize()d keys,
        # with the unredirected ones kept apart; header_items() merges both
        headers = {name.lower(): _header_value(value) for name, value in self._request.header_items()}
        headers.pop("cookie", None)
        return headers

    @property
    def cookies(
        self,
    ) -> str | None:
        for name, value in self._request.header_items():
            if name.lower() == "cookie":
                return _header_value(value)
        return None

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
