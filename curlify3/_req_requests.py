from typing import cast

import requests

from curlify3._base import BaseRequestData
from curlify3._types import Body


class RequestsRequest(BaseRequestData[requests.PreparedRequest]):
    _instance_of = requests.PreparedRequest

    def body(self) -> Body:
        body = self._request.body
        if isinstance(body, bytes):
            try:
                return body.decode()
            except UnicodeDecodeError:
                pass
        # requests also accepts an iterable or a file-like object as the body;
        # rendering those has never been supported, hand it over unchanged
        return cast(Body, body)
