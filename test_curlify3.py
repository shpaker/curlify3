import pathlib

from typing import Any

import fastapi
import httpx
import pytest
import requests

from aiohttp import web as aiohttp_web
from aiohttp.test_utils import TestClient

from curlify3 import to_curl, to_curl_async


@pytest.fixture
def aiohttp_app() -> aiohttp_web.Application:
    aiohttp_app = aiohttp_web.Application()

    async def hello(request: aiohttp_web.Request) -> aiohttp_web.Response:
        try:
            data = await to_curl_async(request)
        except Exception as exc:
            print(exc)
            raise
        return aiohttp_web.Response(text=data)

    aiohttp_app.router.add_get('/', hello)
    aiohttp_app.router.add_post('/', hello)
    return aiohttp_app


@pytest.fixture
def fastapi_app() -> fastapi.FastAPI:
    app = fastapi.FastAPI()

    @app.get("/get")
    async def get(request: fastapi.Request) -> fastapi.Response:
        data = await to_curl_async(request)
        return fastapi.Response(content=data)

    @app.post("/post")
    async def post(request: fastapi.Request) -> fastapi.Response:
        data = await to_curl_async(request)
        return fastapi.Response(content=data)

    return app


_BINARY_ATTACHMENT_PATH = pathlib.Path(__file__).parent / "image.png"
_PARAMS = [
    pytest.param(
        httpx.Request(
            method="GET",
            url="https://httpbin.org/get",
        ),
        "curl -H 'host: httpbin.org' https://httpbin.org/get",
        id="HEADER",
    ),
    pytest.param(
        httpx.Request(
            method="GET",
            url="https://httpbin.org/get",
            params={"foo": 911, "bar": "baz"},
        ),
        "curl -H 'host: httpbin.org' 'https://httpbin.org/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        httpx.Request(
            method="GET",
            url="https://httpbin.org/get",
            cookies={"bar": "baz"},
        ),
        "curl -b bar=baz -H 'host: httpbin.org' https://httpbin.org/get",
        id="COOKIE",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            content=b"foo",
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: plain/text' -d 'foo' https://httpbin.org/post",
        id="TEXT",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            data={"bar": "baz", "abc": "123"},
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: application/x-www-form-urlencoded' -d 'bar=baz&abc=123' https://httpbin.org/post",
        id="FORM",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            json={"bar": "baz"},
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: application/json' -d '{\"bar\": \"baz\"}' https://httpbin.org/post",
        id="JSON",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: multipart/form-data; boundary={boundary}' -F 'image=@image.png' https://httpbin.org/post",
        id="FILE",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
            data={"foo": "bar"},
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: multipart/form-data; boundary={boundary}' -F 'foo=bar' -F 'image=@image.png' https://httpbin.org/post",
        id="FILE + FORM",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _PARAMS,
)
def test_httpx_to_curl(
    req: httpx.Request,
    expected: str,
) -> None:
    results = to_curl(req)
    if (content_type := req.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


@pytest.mark.parametrize(
    "req, expected",
    _PARAMS,
)
@pytest.mark.asyncio
async def test_httpx_async_to_curl(
    req: httpx.Request,
    expected: str,
) -> None:
    results = await to_curl_async(req)
    if (content_type := req.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


@pytest.mark.parametrize(
    "req, expected",
    [
        pytest.param(
            requests.Request(
                method="GET",
                url="https://httpbin.org/get",
            ),
            "curl https://httpbin.org/get",
            id="HEADER",
        ),
        pytest.param(
            requests.Request(
                method="GET",
                url="https://httpbin.org/get",
                params={"foo": 911, "bar": "baz"},
            ),
            "curl 'https://httpbin.org/get?foo=911&bar=baz'",
            id="PARAMS",
        ),
        pytest.param(
            requests.Request(
                method="GET",
                url="https://httpbin.org/get",
                cookies={"bar": "baz"},
            ),
            "curl -b bar=baz https://httpbin.org/get",
            id="COOKIE",
        ),
        pytest.param(
            requests.Request(
                method="POST",
                url="https://httpbin.org/post",
                data={"bar": "baz", "abc": "123"},
            ),
            "curl -X POST -H 'content-type: application/x-www-form-urlencoded' -d 'bar=baz&abc=123' https://httpbin.org/post",
            id="FORM",
        ),
        pytest.param(
            requests.Request(
                method="POST",
                url="https://httpbin.org/post",
                data="foo",
            ),
            "curl -X POST -H 'content-type: plain/text' -d 'foo' https://httpbin.org/post",
            id="TEXT",
        ),
        pytest.param(
            requests.Request(
                method="POST",
                url="https://httpbin.org/post",
                json={"bar": "baz"},
            ),
            "curl -X POST -H 'content-type: application/json' -d '{\"bar\": \"baz\"}' https://httpbin.org/post",
            id="JSON",
        ),
        pytest.param(
            requests.Request(
                method="POST",
                url="https://httpbin.org/post",
                files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
            ),
            "curl -X POST -H 'content-type: multipart/form-data; boundary={boundary}' -F 'image=@image.png' https://httpbin.org/post",
            id="FILE",
        ),
        pytest.param(
            requests.Request(
                method="POST",
                url="https://httpbin.org/post",
                files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
                data={"foo": "bar"},
            ),
            "curl -X POST -H 'content-type: multipart/form-data; boundary={boundary}' -F 'foo=bar' -F 'image=@image.png' https://httpbin.org/post",
            id="FILE + FORM",
        ),
    ],
)
def test_requests_to_curl(
    req: requests.Request,
    expected: str,
) -> None:
    prepared = req.prepare()
    results = to_curl(prepared)
    if (content_type := prepared.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


@pytest.mark.parametrize(
    "req, expected",
    _PARAMS,
)
@pytest.mark.asyncio
async def test_starlette_async_to_curl(
    fastapi_app: fastapi.FastAPI,
    req: httpx.Request,
    expected: str,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app),
        base_url="http://test/get",
    ) as client:
        response = await client.send(req)
    assert response.status_code == 200, response.status_code
    results = response.text
    if (content_type := req.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


@pytest.mark.parametrize(
    "req, expected",
    [
        pytest.param(
            dict(
                method="GET",
            ),
            "curl -H 'host: {server}' {additional_headers} http://{server}/",
            id="HEADER",
        ),
        pytest.param(
            dict(
                method="GET",
                params={"foo": 911, "bar": "baz"},
            ),
            "curl -H 'host: {server}' {additional_headers} 'http://{server}/?foo=911&bar=baz'",
            id="PARAMS",
        ),
        pytest.param(
            dict(
                method="GET",
                cookies={"bar": "baz"},
            ),
            "curl -b bar=baz -H 'host: {server}' {additional_headers} http://{server}/",
            id="COOKIE",
        ),
        pytest.param(
            dict(
                method="POST",
                data=b"foo",
            ),
            "curl -X POST -H 'host: {server}' {additional_headers} -H 'content-type: application/octet-stream' -d 'foo' http://{server}/",
            id="TEXT",
        ),
        pytest.param(
            dict(
                method="POST",
                data={"bar": "baz", "abc": "123"},
            ),
            "curl -X POST -H 'host: {server}' {additional_headers} -H 'content-type: application/x-www-form-urlencoded' -d 'bar=baz&abc=123' http://{server}/",
            id="FORM",
        ),
        pytest.param(
            dict(
                method="POST",
                json={"bar": "baz"},
            ),
            "curl -X POST -H 'host: {server}' {additional_headers} -H 'content-type: application/json' -d '{{\"bar\": \"baz\"}}' http://{server}/",
            id="JSON",
        ),
        # pytest.param(
        #     dict(
        #         method="POST",
        #         data={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
        #     ),
        #     "curl -X POST -H 'host: {server}' {additional_headers} -H 'content-type: multipart/form-data; boundary=boundary' -F 'image=@image.png' http://{server}/",
        #     id="FILE",
        # ),
        # pytest.param(
        #     dict(
        #         method="POST",
        #         data={"foo": "bar", "image": open(_BINARY_ATTACHMENT_PATH, "rb")},
        #     ),
        #     "curl -X POST -H 'host: {server}' {additional_headers} -H 'content-type: multipart/form-data; boundary=boundary' -F 'foo=bar' -F 'image=@image.png' http://{server}/",
        #     id="FILE + FORM",
        # ),
    ],
)
@pytest.mark.asyncio
async def test_aiohttp_async_to_curl(
    aiohttp_app: aiohttp_web.Application,
    aiohttp_client,
    req: dict[str, Any],
    expected: str,
) -> None:
    additional_headers = (
        "-H 'accept: */*' -H 'accept-encoding: gzip, deflate' -H 'user-agent: Python/3.11 aiohttp/3.10.10'"
    )
    client: TestClient = await aiohttp_client(aiohttp_app)
    response = await client.request(path='/', **req)
    results = await response.text()
    assert response.status == 200, response.status
    args = dict(
        server=f'{client.host}:{client.port}',
        additional_headers=additional_headers,
    )
    expected = expected.format(**args)
    assert results == expected, results
