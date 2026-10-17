"""Adapters for tornado: the client HTTPRequest and the server HTTPServerRequest.

Client-side:

    import tornado.httpclient
    from curlify3 import to_curl

    req = tornado.httpclient.HTTPRequest(
        "https://httpbin.org/post",
        method="POST",
        body='{"hello": "world"}',
    )

    print(to_curl(req))

Server-side, the framework reads the body before the handler runs, so the
incoming request renders synchronously:

    import tornado.web
    from curlify3 import to_curl

    class EchoHandler(tornado.web.RequestHandler):
        def post(self):
            self.write({"curl": to_curl(self.request)})
"""

import base64

from collections.abc import Iterable
from typing import Any

from tornado.httpclient import HTTPRequest
from tornado.httputil import HTTPHeaders, HTTPServerRequest, encode_username_password

from curlify3._base import BaseRequestData
from curlify3._types import Body, Headers


def _tornado_header_items(
    headers: Any,  # noqa: ANN401
) -> Iterable[tuple[Any, Any]]:
    # HTTPHeaders joins a repeated header with "," in items(), a Cookie included, and keeps
    # the pairs apart in get_all(); the client request may hold a plain dict instead
    return headers.get_all() if isinstance(headers, HTTPHeaders) else headers.items()


class TornadoRequest(BaseRequestData[HTTPRequest]):
    _instance_of = HTTPRequest

    def _header_items(
        self,
    ) -> Iterable[tuple[Any, Any]]:
        return _tornado_header_items(self._request.headers)

    @property
    def headers(
        self,
    ) -> Headers:
        # the client sets these from the request's own attributes when it sends it, over any
        # header of the same name; the client-wide defaults (a None attribute) are not the
        # request's to know, so only what was set on it is rendered
        headers = super().headers
        request = self._request
        if request.auth_username is not None and request.auth_mode in (None, "basic"):
            credentials = encode_username_password(request.auth_username, request.auth_password or "")
            headers["authorization"] = "Basic " + base64.b64encode(credentials).decode()
        if request.user_agent:
            headers["user-agent"] = request.user_agent
        if request.decompress_response:
            headers["accept-encoding"] = "gzip"
        if request.method == "POST":
            headers.setdefault("content-type", "application/x-www-form-urlencoded")
        return headers

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

    def _header_items(
        self,
    ) -> Iterable[tuple[Any, Any]]:
        return _tornado_header_items(self._request.headers)

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
