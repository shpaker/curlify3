from typing import Any, Protocol, TypeAlias

# a body reaches the curl builder as text when it decodes, and raw otherwise
Body: TypeAlias = str | bytes | None
Headers: TypeAlias = dict[str, str]


class _CommonRequestData(Protocol):
    # everything the curl builder needs from an adapter except the body
    @property
    def http2(self) -> bool: ...

    @property
    def url(self) -> str: ...

    @property
    def method(self) -> str: ...

    @property
    def headers(self) -> Headers: ...

    @property
    def cookies(self) -> str | None: ...


class RequestData(_CommonRequestData, Protocol):
    def body(self) -> Body: ...


class AsyncRequestData(_CommonRequestData, Protocol):
    async def body(self) -> Body: ...


class RawRequest(Protocol):
    # the shape shared by the request objects the adapters wrap; the libraries
    # disagree on the details (requests declares method as str | None, and each
    # one brings its own url and headers containers), so these three stay Any
    # and the adapters normalise whatever comes out of them
    @property
    def url(self) -> Any: ...  # noqa: ANN401

    @property
    def method(self) -> Any: ...  # noqa: ANN401

    @property
    def headers(self) -> Any: ...  # noqa: ANN401
