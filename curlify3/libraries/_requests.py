from typing import Any, Optional, Union

import requests

from curlify3._base import BaseRequestData


class RequestsRequest(
    BaseRequestData
):
    _instance_of = requests.PreparedRequest

    def body(
        self,
    ) -> Optional[Union[bytes, str]]:
        body = self._request.body
        if isinstance(body, bytes):
            try:
               return body.decode()
            except UnicodeDecodeError:
                pass
        return body
