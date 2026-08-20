from typing import Any

from tornado.httpclient import HTTPRequest
from tornado.httputil import HTTPServerRequest

from curlify3._base import BaseRequestData
from curlify3._types import Body


class TornadoRequest(BaseRequestData[HTTPRequest]):
    _instance_of = HTTPRequest

    def body(
        self,
    ) -> Body:
        # the body setter utf8-encodes a str, so bytes | None is all that can
        # come out of the attribute
        body = self._request.body
        if body is None:
            return None
        try:
            return body.decode()
        except UnicodeDecodeError:
            pass
        return body


# HTTPServerRequest falls outside the RawRequest protocol — the absolute url is
# assembled by full_url(), not held in a url attribute — so the type parameter
# stays Any and url is overridden
class TornadoServerRequest(BaseRequestData[Any]):
    _instance_of = HTTPServerRequest

    @property
    def url(
        self,
    ) -> str:
        return self._request.full_url()

    def body(
        self,
    ) -> Body:
        # the framework reads the stream before the handler runs, so the body
        # is already buffered bytes (b"" when there is none)
        data = self._request.body
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
