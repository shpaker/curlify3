import pathlib
import sys

from typing import Any

import aiohttp
import fastapi
import httpx
import httpx2
import pytest
import requests

from aiohttp import web as aiohttp_web
from pytest_aiohttp.plugin import AiohttpClient

from curlify3 import POWERSHELL, to_curl, to_curl_async
from curlify3._curl import quote_powershell

# imported directly so a broken adapter module fails collection loudly instead
# of quietly disappearing from the registries under suppress(ImportError)
from curlify3._req_aiohttp import AiohttpServerRequest
from curlify3._req_httpx import AsyncHttpxRequest, HttpxRequest
from curlify3._req_httpx2 import AsyncHttpx2Request, Httpx2Request
from curlify3._req_requests import RequestsRequest
from curlify3._req_starlette import StarletteRequest
from curlify3._utils import _REQUEST_DATA_CLASSES, _REQUEST_DATA_CLASSES_ASYNC


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
    # requests declares its header values as str | bytes, multipart ones are str
    content_type = prepared.headers.get("content-type")
    if isinstance(content_type, str) and "boundary" in content_type:
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
        "curl --http2 -X POST -H 'host: httpbin.org' -H 'content-type: plain/text' -d 'foo' https://httpbin.org/post",
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
        'curl.exe --% -X POST -H "host: httpbin.org" -H "content-type: plain/text" -d "it\'s" "https://httpbin.org/post"',
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


def test_to_curl_pretty_powershell() -> None:
    req = httpx.Request(method="GET", url="https://httpbin.org/get")
    with pytest.raises(ValueError, match="pretty output is not supported"):
        to_curl(req, shell=POWERSHELL, pretty=True)


def test_request_data_registries() -> None:
    # _utils registers every adapter under suppress(ImportError), so a broken
    # adapter module drops out of the registry silently and only shows up as an
    # unrelated "unknown request object" later. The order is part of the
    # contract too: the first adapter that accepts the request wins.
    assert list(_REQUEST_DATA_CLASSES) == [RequestsRequest, Httpx2Request, HttpxRequest]
    assert list(_REQUEST_DATA_CLASSES_ASYNC) == [
        AsyncHttpx2Request,
        AsyncHttpxRequest,
        AiohttpServerRequest,
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
