import requests

from curlify3._base import BaseRequestData


class RequestsRequest(BaseRequestData):
    _instance_of = requests.PreparedRequest

    def body(self):
        body = self._request.body
        if isinstance(body, bytes):
            try:
                return body.decode()
            except UnicodeDecodeError:
                pass
        return body
