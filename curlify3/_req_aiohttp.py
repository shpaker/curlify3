from aiohttp import ClientRequest, Payload, web

from curlify3._base import AsyncBaseRequestData
from curlify3._types import Body


class AiohttpServerRequest(AsyncBaseRequestData[web.Request]):
    _instance_of = web.Request

    async def body(
        self,
    ) -> Body:
        data = await self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data


async def _payload_bytes(
    data: Payload,
) -> bytes | None:
    # as_bytes (aiohttp >= 3.12.1) reads without consuming: in-memory payloads
    # hand back their stored value, file payloads seek back afterwards, and
    # async iterables cache the chunks and replay them when the request is sent
    try:
        raw = await data.as_bytes()
    except (TypeError, NotImplementedError):
        # a genuinely one-shot payload (@aiohttp.streamer): reading it here
        # would break the request that is about to go out
        return None
    except AttributeError:
        # aiohttp < 3.12.1 has no as_bytes(); only the in-memory payloads are
        # safe to read there — decoding a file payload would move the stream
        # position and corrupt the send
        raw = getattr(data, "_value", None)
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            return None
    # BytesPayload hands back its stored value as is, which can be a bytearray
    # or a memoryview when the request was built from one
    return raw if isinstance(raw, bytes) else bytes(raw)


# the client-side request, reachable in client middlewares (aiohttp >= 3.12):
# ClientSession(middlewares=(mw,)) with async def mw(request, handler)
class AiohttpClientRequest(AsyncBaseRequestData[ClientRequest]):
    _instance_of = ClientRequest

    async def body(
        self,
    ) -> Body:
        body = self._request.body
        # an absent body is spelled b"", anything else is a Payload. A payload
        # built with compress= comes back uncompressed here while the rendered
        # content-encoding header claims otherwise — rare enough to leave be
        data = await _payload_bytes(body) if isinstance(body, Payload) else body
        if data is None:
            return None
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
