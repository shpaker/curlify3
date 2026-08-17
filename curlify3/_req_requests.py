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
                return body
        if body is None or isinstance(body, str):
            return body
        # requests also accepts an iterable or a file-like object as the body.
        # Streaming payloads are not among the supported ones and the object has
        # no textual form a shell could run, so the command carries no -d.
        return None
