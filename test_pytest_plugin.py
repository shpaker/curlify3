"""The pytest plugin, run against generated test files through pytester."""

import fastapi.testclient
import httpcore
import httpx
import httpx2
import niquests
import pytest
import requests

import curlify3.pytest_plugin

pytest_plugins = ["pytester"]

# runpytest() runs in this process and drops every module the inner session
# imported once it is done, so a client imported anew in the next run would
# raise exceptions, and be a class, the previous import knew nothing about —
# everything the inner runs touch is imported here, once, up front
_PRELOADED = (curlify3.pytest_plugin, fastapi.testclient, httpcore, httpx2, niquests)

# loads the plugin the way a user would, and serves every path with the status
# it names: /status/422 answers 422
_CONFTEST = """
import threading

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest_plugins = ["curlify3.pytest_plugin"]


class Handler(BaseHTTPRequestHandler):
    def _answer(self):
        self.rfile.read(int(self.headers.get("content-length") or 0))
        self.send_response(int(self.path.rsplit("/", 1)[-1]))
        self.send_header("content-length", "0")
        self.end_headers()

    do_GET = _answer
    do_POST = _answer

    def log_message(self, format, *args):
        pass


@pytest.fixture
def server_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
"""

_FAILING_HTTPX_TEST = """
import httpcore
import httpx

def test_fails(server_url):
    httpx.post(server_url + "/status/422", json={"qty": 2})
    assert False
"""


@pytest.fixture
def conftest(
    pytester: pytest.Pytester,
    monkeypatch: pytest.MonkeyPatch,
) -> pytest.Pytester:
    pytester.makeconftest(_CONFTEST)
    # the inner runs have no async tests, and pytest-asyncio warns about its
    # unset loop scope in every one of them
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p no:aiohttp -p no:asyncio")
    return pytester


def test_failing_test_gets_section(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        _FAILING_HTTPX_TEST
        + """
def test_passes(server_url):
    httpx.get(server_url + "/status/200")
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*- Captured curl call -*",
            "# [1] 422",
            "curl -X POST * -d '{\"qty\":2}' http://127.0.0.1:*/status/422",
        ]
    )
    # the passing test sent a GET, and only the failing one is reported
    assert "/status/200" not in result.stdout.str()


def test_off_by_default(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(_FAILING_HTTPX_TEST)
    result = conftest.runpytest()
    result.assert_outcomes(failed=1)
    assert "Captured curl" not in result.stdout.str()


def test_ini_turns_it_on(
    conftest: pytest.Pytester,
) -> None:
    conftest.makeini("[pytest]\ncurl_on_failure = true\n")
    conftest.makepyfile(_FAILING_HTTPX_TEST)
    result = conftest.runpytest()
    result.stdout.fnmatch_lines(["*- Captured curl call -*", "# [1] 422"])


def test_fixture_turns_it_on_for_one_test(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import httpcore
import httpx

def test_with_fixture(server_url, curl_requests):
    httpx.get(server_url + "/status/200")
    assert len(curl_requests) == 1
    assert curl_requests[0].startswith("curl ")
    assert curl_requests[0].endswith(server_url + "/status/200")
    assert False

def test_without_fixture(server_url):
    httpx.get(server_url + "/status/500")
    assert False
"""
    )
    result = conftest.runpytest()
    result.assert_outcomes(failed=2)
    result.stdout.fnmatch_lines(["*- Captured curl call -*", "# [1] 200"])
    # the test source in the traceback names the url too, the section would number it
    assert "# [1] 500" not in result.stdout.str()


def test_fixture_with_flag_shares_the_capture(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import httpcore
import httpx

def test_both(server_url, curl_requests):
    httpx.get(server_url + "/status/200")
    httpx.get(server_url + "/status/201")
    assert len(curl_requests) == 2
"""
    )
    conftest.runpytest("--curl-on-failure").assert_outcomes(passed=1)


def test_several_requests_are_numbered(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import httpcore
import httpx
import pytest

def test_flow(server_url):
    httpx.post(server_url + "/status/200", json={"user": "a"})
    httpx.post(server_url + "/status/201", json={"item": "book"})
    with pytest.raises(httpx.ConnectError):
        httpx.get("http://127.0.0.1:9/unreachable")
    httpx.post(server_url + "/status/422", json={"qty": 2})
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.stdout.fnmatch_lines(
        [
            "*- Captured curl call -*",
            "# [1] 200",
            "curl *status/200",
            "# [2] 201",
            "curl *status/201",
            "# [3] ConnectError",
            "curl *127.0.0.1:9/unreachable",
            "# [4] 422",
            "curl *status/422",
        ]
    )


def test_max_requests_keeps_the_last(
    conftest: pytest.Pytester,
) -> None:
    conftest.makeini("[pytest]\ncurl_max_requests = 2\n")
    conftest.makepyfile(
        """
import httpcore
import httpx

def test_loop(server_url):
    for status in (200, 201, 202):
        httpx.get(f"{server_url}/status/{status}")
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.stdout.fnmatch_lines(
        [
            "*- Captured curl call -*",
            "# ... 1 earlier requests omitted",
            "# [2] 201",
            "curl *status/201",
            "# [3] 202",
            "curl *status/202",
        ]
    )
    assert "# [1] 200" not in result.stdout.str()


def test_max_requests_zero_lists_all(
    conftest: pytest.Pytester,
) -> None:
    conftest.makeini("[pytest]\ncurl_max_requests = 0\n")
    conftest.makepyfile(
        """
import httpcore
import httpx

def test_loop(server_url):
    for _ in range(25):
        httpx.get(server_url + "/status/200")
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.stdout.fnmatch_lines(["# [1] 200", "*", "# [25] 200"])
    assert "omitted" not in result.stdout.str()


@pytest.mark.parametrize(
    "value",
    ["-1", "many"],
)
def test_max_requests_rejects_bad_values(
    conftest: pytest.Pytester,
    value: str,
) -> None:
    conftest.makeini(f"[pytest]\ncurl_max_requests = {value}\n")
    conftest.makepyfile("def test_nothing(): pass")
    result = conftest.runpytest()
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*curl_max_requests must be a non-negative integer*"])


def test_exclude_headers(
    conftest: pytest.Pytester,
) -> None:
    conftest.makeini("[pytest]\ncurl_exclude_headers =\n    authorization\n    user-agent\n")
    conftest.makepyfile(
        """
import httpcore
import httpx

def test_auth(server_url):
    httpx.get(server_url + "/status/401", headers={"Authorization": "Bearer t0ken", "X-Trace": "1"})
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    output = result.stdout.str()
    assert "-H 'x-trace: 1'" in output
    # the rendered names are lowercased, the test source in the traceback is not
    assert "-H 'authorization" not in output
    assert "-H 'user-agent" not in output


def test_unrenderable_request_does_not_fail_the_test(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import httpcore
import httpx

def test_nul_body(server_url):
    # a NUL byte has no spelling in a command-line argument, to_curl refuses it
    httpx.post(server_url + "/status/200", content=b"a\\x00b")
    assert False, "the test's own failure"
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        [
            "*the test's own failure*",
            "*- Captured curl call -*",
            "# [1] 200",
            "# not rendered: ValueError(*",
        ]
    )


def test_setup_requests_are_captured(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import httpcore
import httpx
import pytest

@pytest.fixture
def logged_in(server_url):
    httpx.post(server_url + "/status/200", json={"user": "a"})

def test_after_login(server_url, logged_in):
    httpx.get(server_url + "/status/403")
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.stdout.fnmatch_lines(["*- Captured curl call -*", "# [1] 200", "*", "# [2] 403"])


def test_httpx_async(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import asyncio

import httpcore
import httpx

def test_async(server_url):
    async def main():
        async with httpx.AsyncClient() as client:
            await client.post(server_url + "/status/500", data={"a": "1"})

    asyncio.run(main())
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.stdout.fnmatch_lines(["# [1] 500", "curl -X POST * -d 'a=1' *status/500"])


def test_httpx2(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import asyncio

import httpx2

def test_sync_and_async(server_url):
    with httpx2.Client() as client:
        client.get(server_url + "/status/200")

    async def main():
        async with httpx2.AsyncClient() as client:
            await client.get(server_url + "/status/201")

    asyncio.run(main())
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.stdout.fnmatch_lines(["# [1] 200", "curl --http2 *status/200", "# [2] 201", "curl --http2 *status/201"])


def test_fastapi_test_client(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import fastapi

from fastapi.testclient import TestClient

app = fastapi.FastAPI()

@app.post("/orders", status_code=201)
def create_order(order: dict):
    return order

def test_order():
    resp = TestClient(app).post("/orders", json=[1])
    assert resp.status_code == 201
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    # starlette's TestClient is an httpx2 client, so the command carries --http2;
    # [[] is fnmatch for a literal [
    result.stdout.fnmatch_lines(["# [1] 422", "curl --http2 -X POST * -d '[[]1]' http://testserver/orders"])


def test_requests(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import requests

def test_requests(server_url):
    requests.post(server_url + "/status/400", json={"qty": 2})
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.stdout.fnmatch_lines(["# [1] 400", "curl -X POST * -d '{\"qty\": 2}' http://127.0.0.1:*/status/400"])


def test_niquests(
    conftest: pytest.Pytester,
) -> None:
    conftest.makepyfile(
        """
import asyncio

import niquests

def test_sync_and_async(server_url):
    niquests.get(server_url + "/status/200")

    async def main():
        async with niquests.AsyncSession() as session:
            await session.get(server_url + "/status/201")

    asyncio.run(main())
    assert False
"""
    )
    result = conftest.runpytest("--curl-on-failure")
    result.stdout.fnmatch_lines(["# [1] 200", "curl *status/200", "# [2] 201", "curl *status/201"])


def test_send_is_restored(
    conftest: pytest.Pytester,
) -> None:
    sends = (httpx.Client.send, httpx.AsyncClient.send, requests.Session.send)
    conftest.makepyfile(_FAILING_HTTPX_TEST)
    conftest.runpytest("--curl-on-failure").assert_outcomes(failed=1)
    assert (httpx.Client.send, httpx.AsyncClient.send, requests.Session.send) == sends
