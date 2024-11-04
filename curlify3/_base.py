from abc import ABC, abstractmethod


class BaseRequestData(ABC):

    def __init__(self, request) -> None:
        if not isinstance(request, self._instance_of):
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

    @abstractmethod
    def body(self):
        raise NotImplementedError


class AsyncBaseRequestData(BaseRequestData, ABC):
    @abstractmethod
    async def body(self):
        raise NotImplementedError
