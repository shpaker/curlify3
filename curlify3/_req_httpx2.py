import httpx2


class _Httpx2RequestBase:
    http2 = True

    def __init__(self, request) -> None:
        if not isinstance(request, httpx2.Request):
            raise ValueError
        self._request = request

    @property
    def url(self):
        return str(self._request.url)

    @property
    def method(self):
        return self._request.method

    @property
    def headers(self):
        headers = {name.lower(): value for name, value in dict(self._request.headers).items()}
        if self._request.headers.get("cookie"):
            del headers["cookie"]
        return headers

    @property
    def cookies(self):
        if "cookie" not in self._request.headers:
            return None
        return self._request.headers.get("cookie")


class Httpx2Request(_Httpx2RequestBase):

    def body(self):
        data = self._request.read()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data


class AsyncHttpx2Request(_Httpx2RequestBase):

    async def body(self):
        data = await self._request.aread()
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
