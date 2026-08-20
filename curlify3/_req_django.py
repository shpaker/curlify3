from typing import Any

from django.http import HttpRequest
from django.http.request import RawPostDataException

from curlify3._base import BaseRequestData
from curlify3._types import Body


# HttpRequest falls outside the RawRequest protocol — the absolute url is
# assembled by build_absolute_uri(), not held in a url attribute — so the type
# parameter stays Any and url is overridden. The body is buffered by the
# framework before the view runs, which is what makes this adapter sync
class DjangoRequest(BaseRequestData[Any]):
    _instance_of = HttpRequest

    @property
    def url(
        self,
    ) -> str:
        return self._request.build_absolute_uri()

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
