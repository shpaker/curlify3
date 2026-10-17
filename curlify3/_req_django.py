"""Adapter for django.http.HttpRequest.

Django buffers the body before the view runs, so the sync to_curl() is enough —
including inside async views. If the stream was consumed without buffering
(multipart parsing, request.read()), the command carries the headers but no -d.

    from django.http import JsonResponse
    from curlify3 import to_curl

    def echo(request):
        return JsonResponse({"curl": to_curl(request)})
"""

from typing import Any

from django.core.exceptions import DisallowedHost
from django.http import HttpRequest
from django.http.request import RawPostDataException

from curlify3._base import BaseRequestData, raw_request_uri
from curlify3._types import Body


# HttpRequest falls outside the RawRequest protocol — the absolute url is
# assembled by build_absolute_uri(), not held in a url attribute — so the type
# parameter stays Any and url is overridden
class DjangoRequest(BaseRequestData[Any]):
    _instance_of = HttpRequest

    @property
    def url(
        self,
    ) -> str:
        # the path is rebuilt from PATH_INFO, which WSGI hands over percent-decoded, so an
        # encoded / comes back as a path separator; the target as it arrived wins when the
        # server keeps it (RAW_URI or REQUEST_URI, as gunicorn and uwsgi do)
        raw_uri = raw_request_uri(self._request.META)
        try:
            return self._request.build_absolute_uri(raw_uri)
        except DisallowedHost:
            # build_absolute_uri() validates the host against ALLOWED_HOSTS. A logger that
            # renders the request before django turns it into a 400 should still get the
            # command the client sent, rather than an exception of its own
            path = raw_uri or self._request.get_full_path()
            return f"{self._request.scheme}://{self._request._get_raw_host()}{path}"

    def body(
        self,
    ) -> Body:
        try:
            data = self._request.body
        except RawPostDataException:
            # the stream was consumed without buffering (multipart parsing,
            # request.read()); nothing recoverable is left, so the command
            # carries no -d
            return None
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
