from pathlib import Path

from fastapi import FastAPI

import fastapi
import httpx
import pytest
import requests

from curlify3 import to_curl
from curlify3.asyncio import to_curl as async_to_curl

_BINARY_ATTACHMENT_PATH = Path(__file__).parent / "image.png"
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
    results = await async_to_curl(req)
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
)-> None:
    prepared = req.prepare()
    results = to_curl(prepared)
    if (content_type := prepared.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


app = FastAPI()


@app.get("/get")
async def read_root(request: fastapi.Request) -> fastapi.Response:
    data = await async_to_curl(request)
    return fastapi.Response(content=data)


@app.post("/post")
async def read_root(request: fastapi.Request) -> fastapi.Response:
    data = await async_to_curl(request)
    return fastapi.Response(content=data)


@pytest.mark.parametrize(
    "req, expected",
    _PARAMS,
)
@pytest.mark.asyncio
async def test_starlette_async_to_curl(
    req: httpx.Request,
    expected: str,
)-> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test/get"
    ) as client:
        response = await client.send(req)
    assert response.status_code == 200, response.status_code
    results = response.text
    if (content_type := req.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results
