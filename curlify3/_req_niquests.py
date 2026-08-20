import niquests

from curlify3._base import BaseRequestData
from curlify3._types import Body


# a deliberate copy of the requests adapter rather than a subclass: niquests is
# a fork, and a self-contained copy keeps any future divergence isolated — the
# same reasoning the httpx2 adapter followed. HTTP/2 and HTTP/3 are negotiated
# on the transport, the prepared request does not know about them, so no --http2
class NiquestsRequest(BaseRequestData[niquests.PreparedRequest]):
    _instance_of = niquests.PreparedRequest

    def body(
        self,
    ) -> Body:
        body = self._request.body
        if isinstance(body, bytes):
            try:
                return body.decode()
            except UnicodeDecodeError:
                return body
        if body is None or isinstance(body, str):
            return body
        # niquests also accepts an iterable or a file-like object as the body.
        # Streaming payloads are not among the supported ones and the object has
        # no textual form a shell could run, so the command carries no -d.
        return None
