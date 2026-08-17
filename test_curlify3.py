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
from curlify3._curl import quote_powershell, quote_sh, quote_sh_bytes, quote_sh_word

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
    ],
)
def test_to_curl_multipart_field_file_reference(
    value: bytes,
    expected: str,
) -> None:
    req = httpx.Request(method="POST", url="https://httpbin.org/post", files={"field": (None, value)})
    assert f" {expected} " in to_curl(req)


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
    "part, expected",
    [
        pytest.param(b'name="f"\r\n\r\nplain', "-F 'f=plain'", id="TEXT FIELD"),
        # a part name or filename in an encoding of its own is spelled as bytes: the shell hands
        # curl the same bytes back, so the field keeps its name and the file its path
        pytest.param(b'name="\xe9"\r\n\r\nv', "-F $'\\xe9=v'", id="FIELD NAME NOT UTF-8"),
        pytest.param(b'name="f"; filename="caf\xe9.bin"', "-F $'f=@caf\\xe9.bin'", id="FILENAME NOT UTF-8"),
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
