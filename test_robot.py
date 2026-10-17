import http.server
import pathlib
import threading

from collections.abc import Iterator

import pytest
import requests

from robot import run as robot_run
from robot.api import ExecutionResult
from robot.result import Keyword

from curlify3 import to_curl
from curlify3.robot import CurlifyLibrary


@pytest.fixture
def prepared() -> requests.PreparedRequest:
    return requests.Request(
        "POST",
        "https://example.com/post",
        headers={"User-Agent": "test", "X-Token": "t0ken"},
        json={"a": 1},
    ).prepare()


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(
        self,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(
        self,
        format: str,
        *args: object,
    ) -> None:
        pass


@pytest.fixture
def server_url() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def test_to_curl_matches_core(
    prepared: requests.PreparedRequest,
) -> None:
    assert CurlifyLibrary().to_curl(prepared) == to_curl(prepared)


def test_to_curl_unwraps_response(
    prepared: requests.PreparedRequest,
) -> None:
    response = requests.Response()
    response.request = prepared
    assert CurlifyLibrary().to_curl(response) == to_curl(prepared)


def test_import_arguments_are_defaults(
    prepared: requests.PreparedRequest,
) -> None:
    library = CurlifyLibrary(pretty=True, long_options=True, exclude_headers=["user-agent"])
    assert library.to_curl(prepared) == to_curl(
        prepared,
        pretty=True,
        long_options=True,
        exclude_headers=["user-agent"],
    )


def test_keyword_arguments_override_defaults(
    prepared: requests.PreparedRequest,
) -> None:
    library = CurlifyLibrary(pretty=True, exclude_headers=["user-agent"])
    assert library.to_curl(prepared, pretty=False, exclude_headers=[]) == to_curl(prepared)
    assert library.to_curl(prepared, include_headers=["x-token"]) == to_curl(
        prepared,
        pretty=True,
        include_headers=["x-token"],
        exclude_headers=["user-agent"],
    )


def test_powershell_default(
    prepared: requests.PreparedRequest,
) -> None:
    assert CurlifyLibrary(shell="powershell").to_curl(prepared) == to_curl(prepared, shell="powershell")


def _messages(
    item: object,
) -> Iterator[str]:
    for child in getattr(item, "body", ()):
        if isinstance(child, Keyword):
            yield from _messages(child)
        elif getattr(child, "type", None) == "MESSAGE":
            yield child.message


def _run_suite(
    tmp_path: pathlib.Path,
    body: str,
    **variables: str,
) -> dict[str, list[str]]:
    suite = tmp_path / "suite.robot"
    suite.write_text(
        "*** Settings ***\n"
        "Library    RequestsLibrary\n"
        "Library    curlify3.robot.CurlifyLibrary"
        "    exclude_headers=${{['user-agent', 'accept-encoding', 'accept', 'connection']}}\n"
        "\n"
        "*** Test Cases ***\n" + body,
    )
    output = tmp_path / "output.xml"
    rc = robot_run(
        str(suite),
        output=str(output),
        log="NONE",
        report="NONE",
        stdout=None,
        console="none",
        variable=[f"{name}:{value}" for name, value in variables.items()],
    )
    result = ExecutionResult(str(output))
    tests = {test.name: test for test in result.suite.all_tests}
    assert rc == 0, {name: test.message for name, test in tests.items()}
    return {name: list(_messages(test)) for name, test in tests.items()}


def test_robot_keywords_end_to_end(
    tmp_path: pathlib.Path,
    server_url: str,
) -> None:
    messages = _run_suite(
        tmp_path,
        "Returns Command\n"
        "    ${resp}=    GET    ${URL}/one\n"
        "    ${cmd}=    To Curl    ${resp}\n"
        "    Should Be Equal    ${cmd}    curl ${URL}/one\n"
        "\n"
        "Logs Command\n"
        "    ${resp}=    GET    ${URL}/two\n"
        "    Log As Curl    ${resp}\n"
        "\n"
        "Logs Session Requests\n"
        "    Create Session    api    ${URL}\n"
        "    Enable Curl Logging    api\n"
        "    Enable Curl Logging    api    long_options=True\n"
        "    GET On Session    api    /three\n"
        "    Disable Curl Logging    api\n"
        "    GET On Session    api    /four\n",
        URL=server_url,
    )
    assert f"curl {server_url}/two" in messages["Logs Command"]
    session_commands = [message for message in messages["Logs Session Requests"] if message.startswith("curl ")]
    # enabling twice replaced the hook, and disabling it stopped the logging
    assert session_commands == [f"curl {server_url}/three"]


def test_enable_curl_logging_unknown_alias(
    tmp_path: pathlib.Path,
) -> None:
    messages = _run_suite(
        tmp_path,
        "Unknown Alias\n"
        "    Run Keyword And Expect Error    *no session with alias 'missing'*\n"
        "    ...    Enable Curl Logging    missing\n",
    )
    assert "Unknown Alias" in messages
