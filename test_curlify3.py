import asyncio
import pathlib
import sys
import urllib.request

from collections.abc import AsyncIterator
from typing import Any

import aiohttp
import fastapi
import flask
import httpx
import httpx2
import niquests
import pytest
import requests
import tornado.httpclient
import tornado.httputil
import werkzeug
import werkzeug.test
import yarl

from aiohttp import web as aiohttp_web
from aiohttp.test_utils import make_mocked_request
from django.conf import settings as django_settings
from django.http import HttpRequest as DjangoHttpRequest
from django.test import RequestFactory
from multidict import CIMultiDict
from pytest_aiohttp.plugin import AiohttpClient

from curlify3 import POWERSHELL, SENSITIVE_HEADERS, to_curl, to_curl_async
from curlify3._curl import quote_powershell, quote_sh, quote_sh_bytes, quote_sh_word

# imported directly so a broken adapter module fails collection loudly instead
# of quietly disappearing from the registries under suppress(ImportError)
from curlify3._req_aiohttp import AiohttpClientRequest, AiohttpServerRequest
from curlify3._req_django import DjangoRequest
from curlify3._req_httpx import AsyncHttpxRequest, HttpxRequest
from curlify3._req_httpx2 import AsyncHttpx2Request, Httpx2Request
from curlify3._req_niquests import NiquestsRequest
from curlify3._req_requests import RequestsRequest
from curlify3._req_starlette import StarletteRequest
from curlify3._req_tornado import TornadoRequest, TornadoServerRequest
from curlify3._req_urllib import UrllibRequest
from curlify3._req_werkzeug import WerkzeugRequest
from curlify3._utils import _REQUEST_DATA_CLASSES, _REQUEST_DATA_CLASSES_ASYNC

# RequestFactory-built requests need configured settings by the time
# build_absolute_uri() validates the host inside to_curl
if not django_settings.configured:
    django_settings.configure(ALLOWED_HOSTS=["testserver"])


@pytest.fixture
def aiohttp_app() -> aiohttp_web.Application:
    aiohttp_app = aiohttp_web.Application()

    async def hello(
        request: aiohttp_web.Request,
    ) -> aiohttp_web.Response:
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
    async def get(
        request: fastapi.Request,
    ) -> fastapi.Response:
        data = await to_curl_async(request)
        return fastapi.Response(content=data)

    @app.post("/post")
    async def post(
        request: fastapi.Request,
    ) -> fastapi.Response:
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
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post",
        id="TEXT",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            content=b"\xff\xfe\x81binary",
        ),
        # a body the adapter could not decode: an ANSI-C literal, and --data-raw so that a
        # body starting with @ is not read by curl as a filename
        r"curl -X POST -H 'host: httpbin.org' -H 'content-type: text/plain' "
        r"--data-raw $'\xff\xfe\x81binary' https://httpbin.org/post",
        id="BINARY",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            json={"name": "O'Brien"},
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: application/json' "
        "-d '{\"name\":\"O'\\''Brien\"}' https://httpbin.org/post",
        id="SINGLE QUOTE",
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
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: application/json' -d '{\"bar\":\"baz\"}' https://httpbin.org/post",
        id="JSON",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: multipart/form-data; boundary={boundary}' -F 'image=@image.png' https://httpbin.org/post",
        id="FILE BIN",
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
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            files={"this-file": open(__file__, "rb")},
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: multipart/form-data; boundary={boundary}' -F 'this-file=@test_curlify3.py' https://httpbin.org/post",
        id="FILE TXT",
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
            "curl -X POST -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post",
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
    # requests declares its header values as str | bytes, multipart ones are str
    content_type = prepared.headers.get("content-type")
    if isinstance(content_type, str) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


_NIQUESTS_PARAMS = [
    pytest.param(
        niquests.Request(
            method="GET",
            url="https://httpbin.org/get",
        ),
        "curl https://httpbin.org/get",
        id="HEADER",
    ),
    pytest.param(
        niquests.Request(
            method="GET",
            url="https://httpbin.org/get",
            # a str value, unlike the requests case: niquests annotates params
            # strictly and an int fails the type check
            params={"foo": "911", "bar": "baz"},
        ),
        "curl 'https://httpbin.org/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        niquests.Request(
            method="GET",
            url="https://httpbin.org/get",
            cookies={"bar": "baz"},
        ),
        "curl -b bar=baz https://httpbin.org/get",
        id="COOKIE",
    ),
    pytest.param(
        niquests.Request(
            method="POST",
            url="https://httpbin.org/post",
            data={"bar": "baz", "abc": "123"},
        ),
        "curl -X POST -H 'content-type: application/x-www-form-urlencoded' -d 'bar=baz&abc=123' https://httpbin.org/post",
        id="FORM",
    ),
    pytest.param(
        niquests.Request(
            method="POST",
            url="https://httpbin.org/post",
            data="foo",
        ),
        "curl -X POST -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post",
        id="TEXT",
    ),
    pytest.param(
        niquests.Request(
            method="POST",
            url="https://httpbin.org/post",
            json={"bar": "baz"},
        ),
        # niquests spells the content type with an explicit charset, unlike requests
        "curl -X POST -H 'content-type: application/json;charset=utf-8' -d '{\"bar\": \"baz\"}' https://httpbin.org/post",
        id="JSON",
    ),
    pytest.param(
        niquests.Request(
            method="POST",
            url="https://httpbin.org/post",
            files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
        ),
        "curl -X POST -H 'content-type: multipart/form-data; boundary={boundary}' -F 'image=@image.png' https://httpbin.org/post",
        id="FILE",
    ),
    pytest.param(
        niquests.Request(
            method="POST",
            url="https://httpbin.org/post",
            files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
            data={"foo": "bar"},
        ),
        "curl -X POST -H 'content-type: multipart/form-data; boundary={boundary}' -F 'foo=bar' -F 'image=@image.png' https://httpbin.org/post",
        id="FILE + FORM",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _NIQUESTS_PARAMS,
)
def test_niquests_to_curl(
    req: niquests.Request,
    expected: str,
) -> None:
    prepared = req.prepare()
    results = to_curl(prepared)
    # niquests declares headers as optional; a prepared request always has them
    content_type = prepared.headers.get("content-type") if prepared.headers is not None else None
    if isinstance(content_type, str) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


def test_niquests_streaming_body_is_dropped() -> None:
    # same contract as the requests adapter: an iterable body has no textual
    # form a shell could run, so the command carries the headers but no -d
    req = niquests.Request(method="POST", url="https://httpbin.org/post", data=iter([b"chunk"])).prepare()
    assert to_curl(req) == "curl -X POST -H 'transfer-encoding: chunked' https://httpbin.org/post"


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
    aiohttp_client: AiohttpClient,
    req: dict[str, Any],
    expected: str,
) -> None:
    client = await aiohttp_client(aiohttp_app)
    response = await client.request(path='/', **req)
    results = await response.text()
    assert response.status == 200, response.status
    accept_encoding = response.request_info.headers.get('Accept-Encoding', 'gzip, deflate')
    user_agent = response.request_info.headers.get(
        'User-Agent', f'Python/3.{sys.version_info.minor} aiohttp/{aiohttp.__version__}'
    )
    additional_headers = f"-H 'accept: */*' -H 'accept-encoding: {accept_encoding}' -H 'user-agent: {user_agent}'"
    args = dict(
        server=f'{client.host}:{client.port}',
        additional_headers=additional_headers,
    )
    expected = expected.format(**args)
    assert results == expected, results


async def _aiohttp_chunks() -> AsyncIterator[bytes]:
    yield b"chunk"


_AIOHTTP_CLIENT_PARAMS = [
    pytest.param(
        dict(
            method="GET",
            url="https://httpbin.org/get",
        ),
        "curl -H 'host: httpbin.org' https://httpbin.org/get",
        id="HEADER",
    ),
    pytest.param(
        dict(
            method="GET",
            url="https://httpbin.org/get",
            params={"foo": 911, "bar": "baz"},
        ),
        "curl -H 'host: httpbin.org' 'https://httpbin.org/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        dict(
            method="GET",
            url="https://httpbin.org/get",
            cookies={"bar": "baz"},
        ),
        "curl -b bar=baz -H 'host: httpbin.org' https://httpbin.org/get",
        id="COOKIE",
    ),
    pytest.param(
        dict(
            method="POST",
            url="https://httpbin.org/post",
            data="foo",
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: text/plain; charset=utf-8' -d 'foo' https://httpbin.org/post",
        id="TEXT",
    ),
    pytest.param(
        dict(
            method="POST",
            url="https://httpbin.org/post",
            headers={"content-type": "application/json"},
            data=b'{"bar": "baz"}',
        ),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: application/json' -d '{\"bar\": \"baz\"}' https://httpbin.org/post",
        id="JSON",
    ),
    pytest.param(
        dict(
            method="POST",
            url="https://httpbin.org/post",
            data=b"\xff\xfe\x81binary",
        ),
        r"curl -X POST -H 'host: httpbin.org' -H 'content-type: application/octet-stream' "
        r"--data-raw $'\xff\xfe\x81binary' https://httpbin.org/post",
        id="BINARY",
    ),
    pytest.param(
        dict(
            method="POST",
            url="https://httpbin.org/post",
            data=_aiohttp_chunks(),
        ),
        # as_bytes() caches the drained chunks, so the body is rendered and the
        # payload still replays when the request is sent
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: application/octet-stream' "
        "-H 'transfer-encoding: chunked' -d 'chunk' https://httpbin.org/post",
        id="CHUNKED",
    ),
]


@pytest.mark.parametrize(
    "req_kwargs, expected",
    _AIOHTTP_CLIENT_PARAMS,
)
@pytest.mark.asyncio
async def test_aiohttp_client_async_to_curl(
    req_kwargs: dict[str, Any],
    expected: str,
) -> None:
    kwargs = dict(req_kwargs)
    req = aiohttp.ClientRequest(
        url=yarl.URL(kwargs.pop("url")),
        # the auto headers vary with the environment, and the point here is
        # the request the caller shaped
        skip_auto_headers=("Accept", "Accept-Encoding", "User-Agent"),
        loop=asyncio.get_running_loop(),
        **kwargs,
    )
    results = await to_curl_async(req)
    assert results == expected, results


@pytest.mark.asyncio
async def test_aiohttp_client_middleware_to_curl(
    aiohttp_client: AiohttpClient,
) -> None:
    # the natural place to reach a ClientRequest is a client middleware
    # (aiohttp >= 3.12); rendering the command must not consume the payload
    # the session is about to send
    app = aiohttp_web.Application()

    async def echo(
        request: aiohttp_web.Request,
    ) -> aiohttp_web.Response:
        return aiohttp_web.Response(body=await request.read())

    app.router.add_post('/', echo)
    captured: list[str] = []

    async def middleware(
        request: aiohttp.ClientRequest,
        handler: aiohttp.ClientHandlerType,
    ) -> aiohttp.ClientResponse:
        captured.append(await to_curl_async(request))
        return await handler(request)

    client = await aiohttp_client(app, middlewares=(middleware,))
    response = await client.post('/', data=b'content')
    assert response.status == 200, response.status
    # the body arrived byte-for-byte, so reading it for the command kept it intact
    assert await response.text() == 'content'
    accept_encoding = response.request_info.headers['Accept-Encoding']
    user_agent = response.request_info.headers['User-Agent']
    server = f'{client.host}:{client.port}'
    assert captured == [
        f"curl -X POST -H 'host: {server}' -H 'accept: */*' "
        f"-H 'accept-encoding: {accept_encoding}' -H 'user-agent: {user_agent}' "
        f"-H 'content-type: application/octet-stream' -d 'content' http://{server}/"
    ], captured


_HTTPX2_PARAMS = [
    pytest.param(
        httpx2.Request(
            method="GET",
            url="https://httpbin.org/get",
        ),
        "curl --http2 -H 'host: httpbin.org' https://httpbin.org/get",
        id="HEADER",
    ),
    pytest.param(
        httpx2.Request(
            method="GET",
            url="https://httpbin.org/get",
            params={"foo": 911, "bar": "baz"},
        ),
        "curl --http2 -H 'host: httpbin.org' 'https://httpbin.org/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        httpx2.Request(
            method="GET",
            url="https://httpbin.org/get",
            cookies={"bar": "baz"},
        ),
        "curl --http2 -b bar=baz -H 'host: httpbin.org' https://httpbin.org/get",
        id="COOKIE",
    ),
    pytest.param(
        httpx2.Request(
            method="POST",
            url="https://httpbin.org/post",
            content=b"foo",
        ),
        "curl --http2 -X POST -H 'host: httpbin.org' -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post",
        id="TEXT",
    ),
    pytest.param(
        httpx2.Request(
            method="POST",
            url="https://httpbin.org/post",
            json={"bar": "baz"},
        ),
        "curl --http2 -X POST -H 'host: httpbin.org' -H 'content-type: application/json' -d '{\"bar\":\"baz\"}' https://httpbin.org/post",
        id="JSON",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _HTTPX2_PARAMS,
)
def test_httpx2_to_curl(
    req: httpx2.Request,
    expected: str,
) -> None:
    results = to_curl(req)
    assert results == expected, results


@pytest.mark.parametrize(
    "req, expected",
    _HTTPX2_PARAMS,
)
@pytest.mark.asyncio
async def test_httpx2_async_to_curl(
    req: httpx2.Request,
    expected: str,
) -> None:
    results = await to_curl_async(req)
    assert results == expected, results


_POWERSHELL_PARAMS = [
    pytest.param(
        httpx.Request(
            method="GET",
            url="https://httpbin.org/get",
        ),
        'curl.exe --% -H "host: httpbin.org" "https://httpbin.org/get"',
        id="HEADER",
    ),
    pytest.param(
        httpx.Request(
            method="GET",
            url="https://httpbin.org/get",
            params={"foo": 911, "bar": "baz"},
        ),
        'curl.exe --% -H "host: httpbin.org" "https://httpbin.org/get?foo=911&bar=baz"',
        id="PARAMS",
    ),
    pytest.param(
        httpx.Request(
            method="GET",
            url="https://httpbin.org/get",
            cookies={"bar": "baz"},
        ),
        'curl.exe --% -b "bar=baz" -H "host: httpbin.org" "https://httpbin.org/get"',
        id="COOKIE",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            json={"date": "2026-08-10", "actionReference": "SEND_TOTAL_FLOW_TO_COUNTERPART"},
        ),
        'curl.exe --% -X POST -H "host: httpbin.org" -H "content-type: application/json" '
        r'-d "{\"date\":\"2026-08-10\",\"actionReference\":\"SEND_TOTAL_FLOW_TO_COUNTERPART\"}" '
        '"https://httpbin.org/post"',
        id="JSON",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            json={"msg": 'say "hi" now'},
        ),
        'curl.exe --% -X POST -H "host: httpbin.org" -H "content-type: application/json" '
        r'-d "{\"msg\":\"say \\\"hi\\\" now\"}" '
        '"https://httpbin.org/post"',
        id="ESCAPED QUOTES",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            content="it's",
        ),
        'curl.exe --% -X POST -H "host: httpbin.org" -H "content-type: text/plain" -d "it\'s" "https://httpbin.org/post"',
        id="SINGLE QUOTE",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            data={"bar": "baz", "abc": "123"},
        ),
        'curl.exe --% -X POST -H "host: httpbin.org" -H "content-type: application/x-www-form-urlencoded" '
        '-d "bar=baz&abc=123" "https://httpbin.org/post"',
        id="FORM",
    ),
    pytest.param(
        httpx.Request(
            method="POST",
            url="https://httpbin.org/post",
            files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
            data={"foo": "bar"},
        ),
        'curl.exe --% -X POST -H "host: httpbin.org" -H "content-type: multipart/form-data; boundary={boundary}" '
        '-F "foo=bar" -F "image=@image.png" "https://httpbin.org/post"',
        id="FILE + FORM",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _POWERSHELL_PARAMS,
)
def test_httpx_to_curl_powershell(
    req: httpx.Request,
    expected: str,
) -> None:
    results = to_curl(req, shell=POWERSHELL)
    if (content_type := req.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


@pytest.mark.parametrize(
    "req, expected",
    _POWERSHELL_PARAMS,
)
@pytest.mark.asyncio
async def test_httpx_async_to_curl_powershell(
    req: httpx.Request,
    expected: str,
) -> None:
    results = await to_curl_async(req, shell=POWERSHELL)
    if (content_type := req.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param("plain", "'plain'", id="PLAIN"),
        pytest.param("", "''", id="EMPTY"),
        pytest.param("it's", r"'it'\''s'", id="SINGLE QUOTE"),
        pytest.param("'", r"''\'''", id="ONLY A QUOTE"),
        pytest.param('{"name": "O\'Brien"}', "'{\"name\": \"O'\\''Brien\"}'", id="JSON SINGLE QUOTE"),
        # a single-quoted word carries every other metacharacter literally
        pytest.param("$HOME `id` $(x) a&b;c", "'$HOME `id` $(x) a&b;c'", id="METACHARACTERS"),
    ],
)
def test_quote_sh(
    value: str,
    expected: str,
) -> None:
    assert quote_sh(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        # left bare, which is what keeps the common command readable
        pytest.param("https://httpbin.org/get", "https://httpbin.org/get", id="URL"),
        pytest.param("http://127.0.0.1:8000/post", "http://127.0.0.1:8000/post", id="URL WITH PORT"),
        pytest.param("bar=baz", "bar=baz", id="COOKIE"),
        # quoted: every one of these breaks or misfires bare
        pytest.param("https://h/i?limit=10", "'https://h/i?limit=10'", id="QUERY, ZSH GLOB"),
        pytest.param("https://h/i?a=1&b=2", "'https://h/i?a=1&b=2'", id="QUERY AMPERSAND"),
        pytest.param("https://h/wiki/Foo_(bar)", "'https://h/wiki/Foo_(bar)'", id="PARENTHESES"),
        pytest.param("http://h/x;id", "'http://h/x;id'", id="COMMAND SEPARATOR"),
        pytest.param("n=O'Brien", r"'n=O'\''Brien'", id="COOKIE SINGLE QUOTE"),
        pytest.param("a b", "'a b'", id="SPACE"),
        pytest.param("x#y", "'x#y'", id="COMMENT"),
        pytest.param("", "''", id="EMPTY"),
    ],
)
def test_quote_sh_word(
    value: str,
    expected: str,
) -> None:
    assert quote_sh_word(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        # a mis-encoded text body stays legible: only the byte that did not decode is escaped
        pytest.param("café".encode("latin-1"), r"$'caf\xe9'", id="LATIN-1 TEXT"),
        pytest.param(b"\xff\xfe\x81binary", r"$'\xff\xfe\x81binary'", id="BINARY"),
        pytest.param(b"a'b", r"$'a\'b'", id="SINGLE QUOTE"),
        pytest.param(b"a\\b", r"$'a\\b'", id="BACKSLASH"),
        # no literal newline may reach the output or pretty mode's continuation would break
        pytest.param(b"a\nb", r"$'a\x0ab'", id="NEWLINE"),
        pytest.param(b"\x7f", r"$'\x7f'", id="DEL"),
    ],
)
def test_quote_sh_bytes(
    value: bytes,
    expected: str,
) -> None:
    assert quote_sh_bytes(value) == expected


def test_quote_sh_bytes_invariants() -> None:
    # every byte a body can hold except NUL, which make_curl_body refuses outright
    quoted = quote_sh_bytes(bytes(range(1, 256)))
    # pure ascii survives being written to a utf-8 script file and pasted into any terminal,
    # and the absence of a newline is what lets the literal sit on a pretty continuation line
    assert quoted.isascii(), quoted
    assert "\n" not in quoted, quoted


@pytest.mark.parametrize(
    "content",
    [
        # a NUL is valid utf-8, so it reaches the builder as text as readily as it does as bytes
        pytest.param(b"a\x00b", id="DECODES AS TEXT"),
        pytest.param(b"a\x00\xffb", id="STAYS BYTES"),
    ],
)
def test_to_curl_nul_body(
    content: bytes,
) -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", content=content)
    with pytest.raises(ValueError, match="NUL byte"):
        to_curl(req)


def test_to_curl_bytes_body_powershell() -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", content=b"\xff\xfe")
    with pytest.raises(ValueError, match="not valid utf-8"):
        to_curl(req, shell=POWERSHELL)


@pytest.mark.parametrize("long_options", [False, True], ids=["short options", "long options"])
def test_to_curl_bytes_body_option_name(
    long_options: bool,
) -> None:
    # --data-raw has no short form, so the option name is the same either way
    req = httpx.Request(method="POST", url="https://httpbin.org/post", content=b"caf\xe9")
    assert " --data-raw $'caf\\xe9'" in to_curl(req, long_options=long_options)


def test_to_curl_bytes_body_pretty() -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", content=b"caf\xe9")
    assert to_curl(req, pretty=True) == (
        "curl https://httpbin.org/post \\\n"
        "  -X POST \\\n"
        "  -H 'host: httpbin.org' \\\n"
        "  -H 'content-type: text/plain' \\\n"
        "  --data-raw $'caf\\xe9'"
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param('{"bar":"baz"}', r'"{\"bar\":\"baz\"}"', id="QUOTES"),
        pytest.param('{"name": "O\'Brien"}', '"{\\"name\\": \\"O\'Brien\\"}"', id="SINGLE QUOTE"),
        pytest.param(r'{"path": "C:\\x"}', r'"{\"path\": \"C:\\x\"}"', id="BACKSLASHES"),
        pytest.param(r'x\"y', r'"x\\\"y"', id="BACKSLASH BEFORE QUOTE"),
        pytest.param("ab\\", r'"ab\\"', id="TRAILING BACKSLASH"),
        pytest.param("a b\\", r'"a b\\"', id="TRAILING BACKSLASH WITH SPACE"),
    ],
)
def test_quote_powershell(
    value: str,
    expected: str,
) -> None:
    assert quote_powershell(value) == expected


def test_to_curl_unknown_shell() -> None:
    req = httpx.Request(method="GET", url="https://httpbin.org/get")
    with pytest.raises(ValueError, match="unknown shell"):
        to_curl(req, shell="fish")


@pytest.mark.asyncio
async def test_to_curl_async_unknown_shell() -> None:
    req = httpx.Request(method="GET", url="https://httpbin.org/get")
    with pytest.raises(ValueError, match="unknown shell"):
        await to_curl_async(req, shell="fish")


@pytest.mark.parametrize(
    "req, expected",
    [
        pytest.param(
            httpx.Request(
                method="GET",
                url="https://httpbin.org/get",
            ),
            "curl https://httpbin.org/get \\\n  -H 'host: httpbin.org'",
            id="SINGLE OPTION",
        ),
        pytest.param(
            httpx.Request(
                method="POST",
                url="https://httpbin.org/post",
                params={"foo": 911, "bar": "baz"},
                json={"bar": "baz"},
            ),
            "curl 'https://httpbin.org/post?foo=911&bar=baz' \\\n"
            "  -X POST \\\n"
            "  -H 'host: httpbin.org' \\\n"
            "  -H 'content-type: application/json' \\\n"
            "  -d '{\"bar\":\"baz\"}'",
            id="JSON",
        ),
    ],
)
def test_httpx_to_curl_pretty(
    req: httpx.Request,
    expected: str,
) -> None:
    results = to_curl(req, pretty=True)
    assert results == expected, results


@pytest.mark.parametrize(
    "req, expected",
    [
        pytest.param(
            httpx.Request(
                method="POST",
                url="https://httpbin.org/post",
                json={"bar": "baz"},
            ),
            "curl --request POST --header 'host: httpbin.org' --header 'content-type: application/json' "
            "--data '{\"bar\":\"baz\"}' https://httpbin.org/post",
            id="JSON",
        ),
        pytest.param(
            httpx.Request(
                method="POST",
                url="https://httpbin.org/post",
                cookies={"bar": "baz"},
                files={"image": open(_BINARY_ATTACHMENT_PATH, "rb")},
            ),
            "curl --request POST --cookie bar=baz --header 'host: httpbin.org' "
            "--header 'content-type: multipart/form-data; boundary={boundary}' "
            "--form 'image=@image.png' https://httpbin.org/post",
            id="COOKIE + FILE",
        ),
    ],
)
def test_httpx_to_curl_long_options(
    req: httpx.Request,
    expected: str,
) -> None:
    results = to_curl(req, long_options=True)
    if (content_type := req.headers.get("content-type")) and "boundary" in content_type:
        boundary = content_type.rsplit("boundary=")[1]
        expected = expected.format(boundary=boundary)
    assert results == expected, results


@pytest.mark.asyncio
async def test_httpx_async_to_curl_pretty_long_options() -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", json={"bar": "baz"})
    results = await to_curl_async(req, pretty=True, long_options=True)
    assert results == (
        "curl https://httpbin.org/post \\\n"
        "  --request POST \\\n"
        "  --header 'host: httpbin.org' \\\n"
        "  --header 'content-type: application/json' \\\n"
        "  --data '{\"bar\":\"baz\"}'"
    ), results


def _filtered_request() -> httpx.Request:
    return httpx.Request(
        method="POST",
        url="https://httpbin.org/post",
        headers={"User-Agent": "ua", "Accept": "*/*"},
        cookies={"bar": "baz"},
        json={"foo": 1},
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        pytest.param(
            {"exclude_headers": ["User-Agent", "HOST"]},
            "curl -X POST -b bar=baz -H 'accept: */*' -H 'content-type: application/json' "
            "-d '{\"foo\":1}' https://httpbin.org/post",
            id="EXCLUDE CASE-INSENSITIVE",
        ),
        pytest.param(
            {"include_headers": ["content-type", "Accept"]},
            "curl -X POST -H 'accept: */*' -H 'content-type: application/json' "
            "-d '{\"foo\":1}' https://httpbin.org/post",
            id="INCLUDE KEEPS ORDER, DROPS COOKIE",
        ),
        pytest.param(
            {"include_headers": []},
            "curl -X POST -d '{\"foo\":1}' https://httpbin.org/post",
            id="EMPTY INCLUDE",
        ),
        pytest.param(
            {"include_headers": ["accept", "host", "user-agent"], "exclude_headers": ["user-agent"]},
            "curl -X POST -H 'host: httpbin.org' -H 'accept: */*' -d '{\"foo\":1}' https://httpbin.org/post",
            id="INCLUDE THEN EXCLUDE",
        ),
        pytest.param(
            {"exclude_headers": ["cookie"]},
            "curl -X POST -H 'host: httpbin.org' -H 'user-agent: ua' -H 'accept: */*' "
            "-H 'content-type: application/json' -d '{\"foo\":1}' https://httpbin.org/post",
            id="EXCLUDE COOKIE",
        ),
        pytest.param(
            {"include_headers": ["Cookie"]},
            "curl -X POST -b bar=baz -d '{\"foo\":1}' https://httpbin.org/post",
            id="INCLUDE COOKIE",
        ),
    ],
)
def test_to_curl_header_filters(
    kwargs: dict[str, Any],
    expected: str,
) -> None:
    results = to_curl(_filtered_request(), **kwargs)
    assert results == expected, results


@pytest.mark.asyncio
async def test_to_curl_async_header_filters() -> None:
    results = await to_curl_async(
        _filtered_request(),
        include_headers=["accept", "user-agent"],
        exclude_headers=["user-agent"],
    )
    assert results == "curl -X POST -H 'accept: */*' -d '{\"foo\":1}' https://httpbin.org/post", results


def test_to_curl_exclude_content_type_keeps_multipart() -> None:
    # the filter hides the -H line only: the body is still taken apart by its boundary
    req = httpx.Request(
        method="POST",
        url="https://httpbin.org/post",
        data={"field": "value"},
        files={"upload": ("a.txt", b"hi")},
    )
    results = to_curl(req, exclude_headers=["content-type"])
    assert results == (
        "curl -X POST -H 'host: httpbin.org' -F 'field=value' -F 'upload=@a.txt' https://httpbin.org/post"
    ), results


def test_to_curl_header_filter_rejects_str() -> None:
    # a str is an Iterable[str] to the type checker, so only the runtime check catches it
    with pytest.raises(TypeError, match="include_headers expects an iterable of header names"):
        to_curl(_filtered_request(), include_headers="accept")
    with pytest.raises(TypeError, match="exclude_headers expects an iterable of header names"):
        to_curl(_filtered_request(), exclude_headers="accept")


def test_to_curl_header_filter_rejects_non_str_names() -> None:
    # a bytes name would never match the str header names and filter nothing in silence
    with pytest.raises(TypeError, match="include_headers expects header names as str, got bytes"):
        to_curl(_filtered_request(), include_headers=[b"accept"])  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="exclude_headers expects header names as str, got int"):
        to_curl(_filtered_request(), exclude_headers=[1])  # ty: ignore[invalid-argument-type]


def _secret_request() -> httpx.Request:
    return httpx.Request(
        method="POST",
        url="https://httpbin.org/post",
        headers={"Authorization": "Bearer t0ken", "X-Api-Key": "k3y", "Accept": "*/*"},
        cookies={"sid": "s3cret", "theme": "dark"},
        json={"foo": 1},
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        pytest.param(
            {},
            "curl -X POST -b 'sid=s3cret; theme=dark' -H 'host: httpbin.org' -H 'authorization: Bearer t0ken' "
            "-H 'x-api-key: k3y' -H 'accept: */*' -H 'content-type: application/json' "
            "-d '{\"foo\":1}' https://httpbin.org/post",
            id="DEFAULT MASKS NOTHING",
        ),
        pytest.param(
            {"mask_headers": ["Authorization"]},
            "curl -X POST -b 'sid=s3cret; theme=dark' -H 'host: httpbin.org' -H 'authorization: Bearer ***' "
            "-H 'x-api-key: k3y' -H 'accept: */*' -H 'content-type: application/json' "
            "-d '{\"foo\":1}' https://httpbin.org/post",
            id="AUTH KEEPS SCHEME, CASE-INSENSITIVE",
        ),
        pytest.param(
            {"mask_headers": ["x-api-key", "cookie"]},
            "curl -X POST -b 'sid=***; theme=***' -H 'host: httpbin.org' -H 'authorization: Bearer t0ken' "
            "-H 'x-api-key: ***' -H 'accept: */*' -H 'content-type: application/json' "
            "-d '{\"foo\":1}' https://httpbin.org/post",
            id="PLAIN HEADER AND COOKIES PER PAIR",
        ),
        pytest.param(
            {"mask_headers": SENSITIVE_HEADERS},
            "curl -X POST -b 'sid=***; theme=***' -H 'host: httpbin.org' -H 'authorization: Bearer ***' "
            "-H 'x-api-key: ***' -H 'accept: */*' -H 'content-type: application/json' "
            "-d '{\"foo\":1}' https://httpbin.org/post",
            id="SENSITIVE HEADERS",
        ),
        pytest.param(
            {"mask_headers": ["authorization"], "exclude_headers": ["authorization", "cookie"]},
            "curl -X POST -H 'host: httpbin.org' -H 'x-api-key: k3y' -H 'accept: */*' "
            "-H 'content-type: application/json' -d '{\"foo\":1}' https://httpbin.org/post",
            id="EXCLUDE WINS OVER MASK",
        ),
        pytest.param(
            {"mask_headers": SENSITIVE_HEADERS, "include_headers": ["authorization"]},
            "curl -X POST -H 'authorization: Bearer ***' -d '{\"foo\":1}' https://httpbin.org/post",
            id="MASK AFTER INCLUDE",
        ),
    ],
)
def test_to_curl_mask_headers(
    kwargs: dict[str, Any],
    expected: str,
) -> None:
    results = to_curl(_secret_request(), **kwargs)
    assert results == expected, results


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param({"Authorization": "t0ken"}, "authorization: ***", id="NO SCHEME"),
        pytest.param({"Authorization": "Basic dXNlcjpwYXNz"}, "authorization: Basic ***", id="BASIC"),
        pytest.param({"Proxy-Authorization": "Bearer t0ken"}, "proxy-authorization: Bearer ***", id="PROXY"),
        pytest.param({"X-Auth-Token": "Bearer t0ken"}, "x-auth-token: ***", id="SCHEME ONLY FOR AUTH HEADERS"),
    ],
)
def test_to_curl_mask_header_value(
    headers: dict[str, str],
    expected: str,
) -> None:
    req = httpx.Request(method="GET", url="https://httpbin.org/get", headers=headers)
    results = to_curl(req, mask_headers=SENSITIVE_HEADERS)
    assert results == f"curl -H 'host: httpbin.org' -H '{expected}' https://httpbin.org/get", results


def test_to_curl_mask_empty_header() -> None:
    # an empty value has nothing to hide, so it keeps the ; spelling curl sends as empty
    req = httpx.Request(method="GET", url="https://httpbin.org/get", headers={"Authorization": ""})
    results = to_curl(req, mask_headers=SENSITIVE_HEADERS)
    assert results == "curl -H 'host: httpbin.org' -H 'authorization;' https://httpbin.org/get", results


def test_to_curl_mask_cookie_without_value() -> None:
    # a pair with no = has no name to keep, so the whole of it is masked
    req = httpx.Request(method="GET", url="https://httpbin.org/get", headers={"Cookie": "sid=s3cret; flag"})
    results = to_curl(req, mask_headers=["cookie"])
    assert results == "curl -b 'sid=***; ***' -H 'host: httpbin.org' https://httpbin.org/get", results


@pytest.mark.asyncio
async def test_to_curl_async_mask_headers() -> None:
    results = await to_curl_async(_secret_request(), mask_headers=SENSITIVE_HEADERS, include_headers=["cookie"])
    assert results == "curl -X POST -b 'sid=***; theme=***' -d '{\"foo\":1}' https://httpbin.org/post", results


def test_to_curl_mask_headers_powershell() -> None:
    results = to_curl(_secret_request(), shell=POWERSHELL, mask_headers=SENSITIVE_HEADERS)
    assert results == (
        'curl.exe --% -X POST -b "sid=***; theme=***" -H "host: httpbin.org" -H "authorization: Bearer ***" '
        '-H "x-api-key: ***" -H "accept: */*" -H "content-type: application/json" '
        '-d "{\\"foo\\":1}" "https://httpbin.org/post"'
    ), results


def test_to_curl_mask_content_type_keeps_multipart() -> None:
    # masking changes the printed value only: the body is still taken apart by its boundary
    req = httpx.Request(
        method="POST",
        url="https://httpbin.org/post",
        data={"field": "value"},
        files={"upload": ("a.txt", b"hi")},
    )
    results = to_curl(req, mask_headers=["content-type"])
    assert results == (
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: ***' -F 'field=value' -F 'upload=@a.txt' "
        "https://httpbin.org/post"
    ), results


def test_to_curl_mask_headers_rejects_bad_names() -> None:
    with pytest.raises(TypeError, match="mask_headers expects an iterable of header names"):
        to_curl(_secret_request(), mask_headers="authorization")
    with pytest.raises(TypeError, match="mask_headers expects header names as str, got bytes"):
        to_curl(_secret_request(), mask_headers=[b"authorization"])  # ty: ignore[invalid-argument-type]


def test_to_curl_pretty_powershell() -> None:
    req = httpx.Request(method="GET", url="https://httpbin.org/get")
    with pytest.raises(ValueError, match="pretty output is not supported"):
        to_curl(req, shell=POWERSHELL, pretty=True)


# RequestFactory builds real WSGIRequest objects without a server; settings
# are configured at the top of the module
_DJANGO_RF = RequestFactory()
_DJANGO_PARAMS = [
    pytest.param(
        _DJANGO_RF.get("/get"),
        "curl http://testserver/get",
        id="GET",
    ),
    pytest.param(
        _DJANGO_RF.get("/get?foo=911&bar=baz", headers={"X-Foo": "bar"}),
        "curl -H 'x-foo: bar' 'http://testserver/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        _DJANGO_RF.get("/get", headers={"Cookie": "bar=baz"}),
        "curl -b bar=baz http://testserver/get",
        id="COOKIE",
    ),
    pytest.param(
        _DJANGO_RF.post("/post", data="foo", content_type="text/plain"),
        "curl -X POST -H 'content-type: text/plain' -d 'foo' http://testserver/post",
        id="TEXT",
    ),
    pytest.param(
        _DJANGO_RF.post("/post", data="bar=baz&abc=123", content_type="application/x-www-form-urlencoded"),
        "curl -X POST -H 'content-type: application/x-www-form-urlencoded' -d 'bar=baz&abc=123' http://testserver/post",
        id="FORM",
    ),
    pytest.param(
        # RequestFactory multipart-encodes a dict body, with a fixed boundary
        _DJANGO_RF.post("/post", data={"bar": "baz"}),
        "curl -X POST -H 'content-type: multipart/form-data; boundary=BoUnDaRyStRiNg' -F 'bar=baz' http://testserver/post",
        id="MULTIPART",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _DJANGO_PARAMS,
)
def test_django_to_curl(
    req: DjangoHttpRequest,
    expected: str,
) -> None:
    results = to_curl(req)
    assert results == expected, results


def test_django_consumed_body_is_dropped() -> None:
    # multipart parsing reads the stream directly, so request.body raises
    # RawPostDataException afterwards; nothing recoverable is left and the
    # command carries the headers but no -F
    request = _DJANGO_RF.post("/post", data={"bar": "baz"})
    _ = request.POST
    assert to_curl(request) == (
        "curl -X POST -H 'content-type: multipart/form-data; boundary=BoUnDaRyStRiNg' http://testserver/post"
    )


def _werkzeug_request(
    **kwargs: Any,  # noqa: ANN401
) -> werkzeug.Request:
    return werkzeug.test.EnvironBuilder(base_url="https://httpbin.org", **kwargs).get_request()


_WERKZEUG_PARAMS = [
    pytest.param(
        _werkzeug_request(path="/get"),
        "curl -H 'host: httpbin.org' https://httpbin.org/get",
        id="GET",
    ),
    pytest.param(
        _werkzeug_request(path="/get", query_string="foo=911&bar=baz", headers={"X-Foo": "bar"}),
        "curl -H 'host: httpbin.org' -H 'x-foo: bar' 'https://httpbin.org/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        _werkzeug_request(path="/get", headers={"Cookie": "bar=baz"}),
        "curl -b bar=baz -H 'host: httpbin.org' https://httpbin.org/get",
        id="COOKIE",
    ),
    pytest.param(
        _werkzeug_request(path="/post", method="POST", data="foo"),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post",
        id="TEXT",
    ),
    pytest.param(
        _werkzeug_request(path="/post", method="POST", data={"bar": "baz", "abc": "123"}),
        "curl -X POST -H 'host: httpbin.org' -H 'content-type: application/x-www-form-urlencoded' -d 'bar=baz&abc=123' https://httpbin.org/post",
        id="FORM",
    ),
    pytest.param(
        _werkzeug_request(path="/post", method="POST", data=b"\xff\xfe\x81binary"),
        r"curl -X POST -H 'host: httpbin.org' -H 'content-type: text/plain' --data-raw $'\xff\xfe\x81binary' https://httpbin.org/post",
        id="BINARY",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _WERKZEUG_PARAMS,
)
def test_werkzeug_to_curl(
    req: werkzeug.Request,
    expected: str,
) -> None:
    results = to_curl(req)
    assert results == expected, results


def test_flask_to_curl() -> None:
    # flask.Request subclasses werkzeug's, so the flask request proxy
    # dispatches to the werkzeug adapter
    app = flask.Flask(__name__)
    with app.test_request_context("/post", base_url="https://httpbin.org", method="POST", data="foo"):
        results = to_curl(flask.request)
    assert (
        results == "curl -X POST -H 'host: httpbin.org' -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post"
    )


_TORNADO_PARAMS = [
    pytest.param(
        tornado.httpclient.HTTPRequest(
            "https://httpbin.org/get",
        ),
        "curl https://httpbin.org/get",
        id="GET",
    ),
    pytest.param(
        tornado.httpclient.HTTPRequest(
            "https://httpbin.org/get?foo=911&bar=baz",
            headers={"X-Foo": "bar"},
        ),
        "curl -H 'x-foo: bar' 'https://httpbin.org/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        # the client request keeps whatever headers container it was handed —
        # here a plain case-sensitive dict — and the cookie still reaches -b
        tornado.httpclient.HTTPRequest(
            "https://httpbin.org/get",
            headers={"Cookie": "bar=baz"},
        ),
        "curl -b bar=baz https://httpbin.org/get",
        id="COOKIE",
    ),
    pytest.param(
        tornado.httpclient.HTTPRequest(
            "https://httpbin.org/post",
            method="POST",
            body="foo",
        ),
        "curl -X POST -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post",
        id="TEXT",
    ),
    pytest.param(
        tornado.httpclient.HTTPRequest(
            "https://httpbin.org/post",
            method="POST",
            body=b"\xff\xfe\x81binary",
        ),
        r"curl -X POST -H 'content-type: text/plain' --data-raw $'\xff\xfe\x81binary' https://httpbin.org/post",
        id="BINARY",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _TORNADO_PARAMS,
)
def test_tornado_to_curl(
    req: tornado.httpclient.HTTPRequest,
    expected: str,
) -> None:
    results = to_curl(req)
    assert results == expected, results


_TORNADO_SERVER_PARAMS = [
    pytest.param(
        tornado.httputil.HTTPServerRequest(
            method="GET",
            uri="/get",
            host="httpbin.org",
        ),
        "curl http://httpbin.org/get",
        id="GET",
    ),
    pytest.param(
        tornado.httputil.HTTPServerRequest(
            method="GET",
            uri="/get?foo=911&bar=baz",
            host="httpbin.org",
            headers=tornado.httputil.HTTPHeaders({"X-Foo": "bar"}),
        ),
        "curl -H 'x-foo: bar' 'http://httpbin.org/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        tornado.httputil.HTTPServerRequest(
            method="GET",
            uri="/get",
            host="httpbin.org",
            headers=tornado.httputil.HTTPHeaders({"Cookie": "bar=baz"}),
        ),
        "curl -b bar=baz http://httpbin.org/get",
        id="COOKIE",
    ),
    pytest.param(
        tornado.httputil.HTTPServerRequest(
            method="POST",
            uri="/post",
            host="httpbin.org",
            headers=tornado.httputil.HTTPHeaders({"Content-Type": "text/plain"}),
            body=b"foo",
        ),
        "curl -X POST -H 'content-type: text/plain' -d 'foo' http://httpbin.org/post",
        id="TEXT",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _TORNADO_SERVER_PARAMS,
)
def test_tornado_server_to_curl(
    req: tornado.httputil.HTTPServerRequest,
    expected: str,
) -> None:
    results = to_curl(req)
    assert results == expected, results


_URLLIB_PARAMS = [
    pytest.param(
        urllib.request.Request(
            "https://httpbin.org/get",
        ),
        "curl https://httpbin.org/get",
        id="GET",
    ),
    pytest.param(
        urllib.request.Request(
            "https://httpbin.org/get?foo=911&bar=baz",
            headers={"X-Foo": "bar"},
        ),
        "curl -H 'x-foo: bar' 'https://httpbin.org/get?foo=911&bar=baz'",
        id="PARAMS",
    ),
    pytest.param(
        urllib.request.Request(
            "https://httpbin.org/get",
            headers={"Cookie": "bar=baz"},
        ),
        "curl -b bar=baz https://httpbin.org/get",
        id="COOKIE",
    ),
    pytest.param(
        # no method given: urllib infers POST for a request carrying data
        urllib.request.Request(
            "https://httpbin.org/post",
            data=b"foo",
        ),
        "curl -X POST -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post",
        id="TEXT",
    ),
    pytest.param(
        urllib.request.Request(
            "https://httpbin.org/post",
            data=b"\xff\xfe\x81binary",
        ),
        r"curl -X POST -H 'content-type: text/plain' --data-raw $'\xff\xfe\x81binary' https://httpbin.org/post",
        id="BINARY",
    ),
    pytest.param(
        urllib.request.Request(
            "https://httpbin.org/delete",
            method="DELETE",
        ),
        "curl -X DELETE https://httpbin.org/delete",
        id="EXPLICIT METHOD",
    ),
]


@pytest.mark.parametrize(
    "req, expected",
    _URLLIB_PARAMS,
)
def test_urllib_to_curl(
    req: urllib.request.Request,
    expected: str,
) -> None:
    results = to_curl(req)
    assert results == expected, results


def test_urllib_streaming_body_is_dropped() -> None:
    # urllib accepts an iterable body too; it has no textual form a shell could
    # run, so the command carries no -d while the method is still inferred POST
    req = urllib.request.Request("https://httpbin.org/post", data=iter([b"chunk"]))
    assert to_curl(req) == "curl -X POST https://httpbin.org/post"


def test_urllib_unredirected_headers_are_rendered() -> None:
    # the urlopen machinery stores Content-Type and friends as unredirected
    # headers, kept apart from the plain header dict; header_items() merges both
    req = urllib.request.Request("https://httpbin.org/post", data=b"foo")
    req.add_unredirected_header("Content-Type", "text/plain")
    assert to_curl(req) == "curl -X POST -H 'content-type: text/plain' -d 'foo' https://httpbin.org/post"


def test_request_data_registries() -> None:
    # _utils registers every adapter under suppress(ImportError), so a broken
    # adapter module drops out of the registry silently and only shows up as an
    # unrelated "unknown request object" later. The order is part of the
    # contract too: the first adapter that accepts the request wins.
    assert list(_REQUEST_DATA_CLASSES) == [
        RequestsRequest,
        NiquestsRequest,
        Httpx2Request,
        HttpxRequest,
        DjangoRequest,
        WerkzeugRequest,
        TornadoRequest,
        TornadoServerRequest,
        UrllibRequest,
    ]
    assert list(_REQUEST_DATA_CLASSES_ASYNC) == [
        AsyncHttpx2Request,
        AsyncHttpxRequest,
        AiohttpServerRequest,
        AiohttpClientRequest,
        StarletteRequest,
    ]


def test_requests_streaming_body_is_dropped() -> None:
    # requests accepts an iterable body, which has no textual form a shell could
    # run — the command carries the headers but no -d
    req = requests.Request(method="POST", url="https://httpbin.org/post", data=iter([b"chunk"])).prepare()
    assert to_curl(req) == "curl -X POST -H 'transfer-encoding: chunked' https://httpbin.org/post"


def test_multipart_content_type_without_body() -> None:
    # a content-type that promises multipart while the request carries no body
    # renders without -F rather than raising
    req = requests.Request(
        method="POST",
        url="https://httpbin.org/post",
        headers={"content-type": "multipart/form-data; boundary=abc"},
    ).prepare()
    assert to_curl(req) == "curl -X POST -H 'content-type: multipart/form-data; boundary=abc' https://httpbin.org/post"


# a leading @ in a --data value, and a leading @ or < in a --form value, name a local file for
# curl to send the contents of. Both are reachable from the wire through the server-side
# adapters, where a command rendered into a log would read a file of the caller's choosing


@pytest.mark.parametrize(
    "content, expected_option",
    [
        # the option has to change: --data would send the contents of /etc/passwd instead
        pytest.param("@/etc/passwd", "--data-raw", id="LEADING AT"),
        # only the first character carries the meaning, so the terse option stays elsewhere
        pytest.param("user@example.com", "-d", id="AT INSIDE"),
        pytest.param("<html>", "-d", id="LEADING LT IS DATA SAFE"),
    ],
)
def test_to_curl_body_file_reference(
    content: str,
    expected_option: str,
) -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", content=content)
    assert f" {expected_option} '{content}'" in to_curl(req)


@pytest.mark.parametrize("long_options", [False, True], ids=["short options", "long options"])
def test_to_curl_body_file_reference_option_name(
    long_options: bool,
) -> None:
    # --data-raw has no short form, so the option name is the same either way
    req = httpx.Request(method="POST", url="https://httpbin.org/post", content="@x")
    assert " --data-raw '@x'" in to_curl(req, long_options=long_options)


def test_to_curl_body_file_reference_powershell() -> None:
    # the dialect renders the same option: --% leaves the value to curl.exe, which reads
    # the leading @ exactly as it does under sh
    req = httpx.Request(method="POST", url="https://httpbin.org/post", content="@x")
    assert ' --data-raw "@x"' in to_curl(req, shell=POWERSHELL)


@pytest.mark.parametrize(
    "value, expected",
    [
        # -F would open the named file and send its contents as the field value
        pytest.param(b"@/etc/passwd", "--form-string 'field=@/etc/passwd'", id="LEADING AT"),
        # < is the other spelling of the same thing, and it is a --form value only
        pytest.param(b"</etc/passwd", "--form-string 'field=</etc/passwd'", id="LEADING LT"),
        pytest.param(b"user@example.com", "-F 'field=user@example.com'", id="AT INSIDE"),
        # -F reads ;headers=@file as a local file to load the part headers from
        pytest.param(b"x;headers=@/etc/passwd", "--form-string 'field=x;headers=@/etc/passwd'", id="HEADERS ATTR"),
        # and ;type= / ;filename= as attributes of the part, sending a shorter value
        pytest.param(b"x;type=text/html", "--form-string 'field=x;type=text/html'", id="TYPE ATTR"),
        pytest.param(b"x;filename=a.txt", "--form-string 'field=x;filename=a.txt'", id="FILENAME ATTR"),
        # a leading " opens a quoted string, whose tail -F drops
        pytest.param(b'"lead" more', "--form-string 'field=\"lead\" more'", id="LEADING QUOTE"),
        pytest.param(b'say "hi"', "-F 'field=say \"hi\"'", id="QUOTE INSIDE"),
    ],
)
def test_to_curl_multipart_field_file_reference(
    value: bytes,
    expected: str,
) -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", files={"field": (None, value)})
    assert f" {expected} " in to_curl(req)


@pytest.mark.parametrize(
    "filename, expected",
    [
        pytest.param(b"a.txt", "-F 'f=@a.txt'", id="PLAIN"),
        # -F cuts a bare filename at a ; (an attribute) or at a , (a list of files)
        pytest.param(b"a;b.txt", "-F 'f=@\"a;b.txt\"'", id="SEMICOLON"),
        pytest.param(b"a,b.txt", "-F 'f=@\"a,b.txt\"'", id="COMMA"),
        # inside the quoted form a \ is escaped with a backslash, as a " would be
        pytest.param(b"a;b\\.txt", "-F 'f=@\"a;b\\\\.txt\"'", id="BACKSLASH"),
    ],
)
def test_to_curl_multipart_filename_quoting(
    filename: bytes,
    expected: str,
) -> None:
    # written as it arrives on the wire: httpx and requests would percent-encode a " themselves
    req = requests.Request(
        method="POST",
        url="https://httpbin.org/post",
        headers={"content-type": "multipart/form-data; boundary=b"},
        data=b'--b\r\nContent-Disposition: form-data; name="f"; filename="' + filename + b'"\r\n\r\nx\r\n--b--\r\n',
    ).prepare()
    assert f" {expected} " in to_curl(req)


@pytest.mark.parametrize(
    "cookie, expected",
    [
        pytest.param("a=1; b=2", "-b 'a=1; b=2'", id="PAIRS"),
        # -b reads a value without an = as the name of a cookie file to send the cookies of
        pytest.param("/etc/cookies.txt", "-H 'cookie: /etc/cookies.txt'", id="NO EQUALS"),
    ],
)
def test_to_curl_cookie_without_pair(
    cookie: str,
    expected: str,
) -> None:
    req = httpx.Request(method="GET", url="https://httpbin.org/get", headers={"cookie": cookie})
    assert f" {expected} " in to_curl(req)


@pytest.mark.parametrize(
    "request_kwargs",
    [
        # --% ends at the line break, so the line after it would run as powershell
        pytest.param(dict(content='a"\nGet-Date; # '), id="BODY LF"),
        pytest.param(dict(content="a\r\nb"), id="BODY CRLF"),
        pytest.param(dict(json={"a": 1}, headers={"x-note": "a\rb"}), id="HEADER CR"),
        pytest.param(dict(files={"note": (None, "a\nb")}), id="MULTIPART FIELD LF"),
    ],
)
def test_to_curl_line_break_powershell(
    request_kwargs: dict[str, Any],
) -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", **request_kwargs)
    with pytest.raises(ValueError, match="line break"):
        to_curl(req, shell=POWERSHELL)


def test_to_curl_multipart_field_bytes_value() -> None:
    # a plain field carrying bytes that are not text: rendered through the same $'...' quoting
    # a body that did not decode uses, rather than raising UnicodeDecodeError
    req = httpx.Request(method="POST", url="https://httpbin.org/post", files={"blob": (None, b"caf\xe9")})
    assert " -F $'blob=caf\\xe9' " in to_curl(req)


def test_to_curl_multipart_field_bytes_value_powershell() -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", files={"blob": (None, b"\xff\xfe")})
    with pytest.raises(ValueError, match="not valid utf-8"):
        to_curl(req, shell=POWERSHELL)


def test_to_curl_multipart_field_nul_value() -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", files={"blob": (None, b"a\x00b")})
    with pytest.raises(ValueError, match="NUL byte"):
        to_curl(req)


def test_to_curl_multipart_single_character_field_name() -> None:
    # the part patterns used to require two characters of a name, which dropped a
    # single-character field from the command without a word
    req = httpx.Request(
        method="POST",
        url="https://httpbin.org/post",
        files={"a": (None, "1"), "long": (None, "2")},
    )
    command = to_curl(req)
    assert " -F 'a=1' " in command
    assert " -F 'long=2' " in command


@pytest.mark.parametrize(
    "value, expected",
    [
        # the value used to be matched as a single line, so it was cut at the first CRLF and
        # the command sent the prefix without a word
        pytest.param("line1\r\nline2", "-F 'note=line1\r\nline2'", id="CRLF"),
        pytest.param("a\nb", "-F 'note=a\nb'", id="LF"),
        # a newline does not stop the value from being a file reference too
        pytest.param("@x\r\ny", "--form-string 'note=@x\r\ny'", id="FILE REF WITH CRLF"),
    ],
)
def test_to_curl_multipart_field_newline_value(
    value: str,
    expected: str,
) -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", files={"note": (None, value)})
    assert f" {expected} " in to_curl(req)


def test_to_curl_multipart_preserves_wire_order() -> None:
    # the parts are rendered in the order the body carries them. The two patterns this replaced
    # ran one after the other, so every plain field came out before every file part whatever
    # order the body put them in
    req = httpx.Request(
        method="POST",
        url="https://httpbin.org/post",
        files={"img": ("i.png", b"x"), "foo": (None, "bar")},
    )
    assert " -F 'img=@i.png' -F 'foo=bar' " in to_curl(req)


@pytest.mark.parametrize(
    "content_type, expected",
    [
        pytest.param("multipart/form-data; boundary=b", " -F 'foo=bar' ", id="BARE"),
        pytest.param('multipart/form-data; boundary="b"', " -F 'foo=bar' ", id="QUOTED"),
        # nothing to take the body apart with, so there are no parts to render — the command a
        # multipart content-type without a body produces
        pytest.param("multipart/form-data", None, id="MISSING"),
    ],
)
def test_to_curl_multipart_boundary(
    content_type: str,
    expected: str | None,
) -> None:
    req = requests.Request(
        method="POST",
        url="https://httpbin.org/post",
        headers={"content-type": content_type},
        data=b'--b\r\nContent-Disposition: form-data; name="foo"\r\n\r\nbar\r\n--b--\r\n',
    ).prepare()
    command = to_curl(req)
    if expected is None:
        assert "-F" not in command
    else:
        assert expected in command


@pytest.mark.parametrize(
    "part, expected",
    [
        pytest.param(b'name="f"\r\n\r\nplain', "-F 'f=plain'", id="TEXT FIELD"),
        # a part name or filename in an encoding of its own is spelled as bytes: the shell hands
        # curl the same bytes back, so the field keeps its name and the file its path
        pytest.param(b'name="\xe9"\r\n\r\nv', "-F $'\\xe9=v'", id="FIELD NAME NOT UTF-8"),
        pytest.param(b'name="f"; filename="caf\xe9.bin"\r\n\r\nx', "-F $'f=@caf\\xe9.bin'", id="FILENAME NOT UTF-8"),
    ],
)
def test_to_curl_multipart_part_not_utf8(
    part: bytes,
    expected: str,
) -> None:
    # an encoding of its own is not something a client would produce — httpx and requests both
    # write utf-8 — so the body is handed over the way it arrives on the wire, which is where the
    # server-side adapters read it from
    req = requests.Request(
        method="POST",
        url="https://httpbin.org/post",
        headers={"content-type": "multipart/form-data; boundary=b"},
        data=b"--b\r\nContent-Disposition: form-data; " + part + b"\r\n--b--\r\n",
    ).prepare()
    assert f" {expected} " in to_curl(req)


def _starlette_request(
    path: str,
    raw_path: bytes | None,
    headers: list[tuple[bytes, bytes]] | None = None,
) -> fastapi.Request:
    # built the way uvicorn builds the scope: path percent-decoded, raw_path as it arrived
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "server": ("testserver", 80),
        "path": path,
        "query_string": b"x=1",
        "headers": [(b"host", b"testserver"), *(headers or [])],
    }
    if raw_path is not None:
        scope["raw_path"] = raw_path

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return fastapi.Request(scope, receive)


@pytest.mark.parametrize(
    "path, raw_path, expected",
    [
        # a space in the decoded path is a url curl rejects
        pytest.param("/a b", b"/a%20b", "http://testserver/a%20b?x=1", id="SPACE"),
        # an encoded /, ? or # comes back decoded as another route, a query or a fragment
        pytest.param("/a/b", b"/a%2Fb", "http://testserver/a%2Fb?x=1", id="SLASH"),
        pytest.param("/a?b", b"/a%3Fb", "http://testserver/a%3Fb?x=1", id="QUESTION MARK"),
        pytest.param("/a#b", b"/a%23b", "http://testserver/a%23b?x=1", id="HASH"),
        # raw_path is optional in the ASGI spec
        pytest.param("/a", None, "http://testserver/a?x=1", id="NO RAW PATH"),
    ],
)
@pytest.mark.asyncio
async def test_starlette_raw_path(
    path: str,
    raw_path: bytes | None,
    expected: str,
) -> None:
    command = await to_curl_async(_starlette_request(path, raw_path))
    assert command == f"curl -H 'host: testserver' '{expected}'"


def test_werkzeug_raw_uri() -> None:
    # werkzeug rebuilds the url from the decoded PATH_INFO, where an encoded / is a separator
    request = _werkzeug_request(path="/a%2Fb", query_string="x=1")
    assert to_curl(request) == "curl -H 'host: httpbin.org' 'https://httpbin.org/a%2Fb?x=1'"


@pytest.mark.parametrize(
    "extra, expected",
    [
        pytest.param({"RAW_URI": "/a%2Fb?x=1"}, "http://testserver/a%2Fb?x=1", id="RAW_URI"),
        pytest.param({"REQUEST_URI": "/a%2Fb?x=1"}, "http://testserver/a%2Fb?x=1", id="REQUEST_URI"),
        # the decoded path is all django has without either, so the %2F is gone
        pytest.param({}, "http://testserver/a/b?x=1", id="NEITHER"),
        # an absolute-form target is not trusted to be the path
        pytest.param({"RAW_URI": "http://evil/x"}, "http://testserver/a/b?x=1", id="ABSOLUTE FORM"),
    ],
)
def test_django_raw_uri(
    extra: dict[str, str],
    expected: str,
) -> None:
    request = RequestFactory().get("/a%2Fb?x=1", **extra)
    assert f" '{expected}'" in to_curl(request)


@pytest.mark.asyncio
async def test_starlette_repeated_headers() -> None:
    # dict() kept only the first value of each: the second x-a and the second cookie were lost
    request = _starlette_request(
        "/",
        b"/",
        [(b"x-a", b"1"), (b"x-a", b"2"), (b"cookie", b"a=1"), (b"cookie", b"b=2")],
    )
    command = await to_curl_async(request)
    assert command == "curl -b 'a=1; b=2' -H 'host: testserver' -H 'x-a: 1, 2' 'http://testserver/?x=1'"


def _tornado_headers(
    pairs: list[tuple[str, str]],
) -> tornado.httputil.HTTPHeaders:
    headers = tornado.httputil.HTTPHeaders()
    for name, value in pairs:
        headers.add(name, value)
    return headers


@pytest.mark.parametrize(
    "req",
    [
        # httpx joins a repeated header with ", " in items(), the cookies included
        pytest.param(
            httpx.Request(
                "GET", "http://h/", headers=[("x-a", "1"), ("x-a", "2"), ("cookie", "a=1"), ("cookie", "b=2")]
            ),
            id="HTTPX",
        ),
        pytest.param(
            httpx2.Request(
                "GET", "http://h/", headers=[("x-a", "1"), ("x-a", "2"), ("cookie", "a=1"), ("cookie", "b=2")]
            ),
            id="HTTPX2",
        ),
        # tornado joins them with ","
        pytest.param(
            tornado.httpclient.HTTPRequest(
                "http://h/",
                headers=_tornado_headers([("x-a", "1"), ("x-a", "2"), ("cookie", "a=1"), ("cookie", "b=2")]),
            ),
            id="TORNADO",
        ),
    ],
)
def test_to_curl_repeated_headers(
    req: object,
) -> None:
    command = to_curl(req)
    # a comma between the cookies runs them together: a server reads cookie a as "1, b=2"
    assert " -b 'a=1; b=2' " in command
    assert " -H 'x-a: 1, 2' " in command


def test_tornado_server_repeated_headers() -> None:
    headers = _tornado_headers([("Host", "h"), ("Cookie", "a=1"), ("Cookie", "b=2")])
    request = tornado.httputil.HTTPServerRequest(method="GET", uri="/", headers=headers)
    assert to_curl(request) == "curl -b 'a=1; b=2' -H 'host: h' http://h/"


@pytest.mark.parametrize(
    "url, globoff",
    [
        # curl expands [] and {} in a url, so the command sends other requests than the one it was rendered from
        pytest.param("http://h/p?a[]=1", True, id="BRACKETS"),
        pytest.param("http://h/p?b={x}", True, id="BRACES"),
        pytest.param("http://h/p?id=[1-3]", True, id="RANGE"),
        pytest.param("http://h/p?a=1", False, id="PLAIN"),
    ],
)
@pytest.mark.parametrize("long_options", [False, True], ids=["short options", "long options"])
def test_to_curl_url_globoff(
    url: str,
    globoff: bool,
    long_options: bool,
) -> None:
    command = to_curl(httpx.Request("GET", url), long_options=long_options)
    option = "--globoff" if long_options else "-g"
    assert (f" {option} " in command) is globoff, command


@pytest.mark.parametrize(
    "shell, expected",
    [
        # curl drops a header passed with nothing after the colon, and sends it with the ; spelling
        pytest.param("sh", " -H 'x-e;' ", id="SH"),
        pytest.param(POWERSHELL, ' -H "x-e;" ', id="POWERSHELL"),
    ],
)
def test_to_curl_empty_header_value(
    shell: str,
    expected: str,
) -> None:
    req = httpx.Request("GET", "http://h/", headers={"x-e": ""})
    assert expected in to_curl(req, shell=shell)


@pytest.mark.asyncio
async def test_aiohttp_repeated_headers() -> None:
    # dict() kept only the first value off the multidict
    headers = CIMultiDict([("Host", "h"), ("X-A", "1"), ("X-A", "2"), ("Cookie", "a=1"), ("Cookie", "b=2")])
    request = make_mocked_request("GET", "/", headers=headers)
    assert await to_curl_async(request) == "curl -b 'a=1; b=2' -H 'host: h' -H 'x-a: 1, 2' http://h/"
