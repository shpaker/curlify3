"""End-to-end checks: the generated command is executed by a real shell and a local
HTTP server verifies that the request arrives byte-for-byte intact.

The PowerShell tests run only on Windows (powershell.exe 5.1, the dialect target);
the sh tests run everywhere else via bash. CI covers both via ubuntu and windows jobs.
"""

import pathlib
import platform
import subprocess
import threading

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, TypeAlias

import httpx
import pytest

from curlify3 import POWERSHELL, SH, to_curl

SUBPROCESS_TIMEOUT = 120

# the base url of the capture server and the requests it has captured
CaptureServer: TypeAlias = tuple[str, list[dict[str, Any]]]


@pytest.fixture
def capture_server() -> Iterator[CaptureServer]:
    captured: list[dict[str, Any]] = []

    class CaptureHandler(BaseHTTPRequestHandler):
        def _capture(
            self,
        ) -> None:
            length = int(self.headers.get("content-length") or 0)
            captured.append(
                {
                    "method": self.command,
                    "path": self.path,
                    "body": self.rfile.read(length),
                }
            )
            self.send_response(200)
            self.send_header("content-length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        do_GET = _capture
        do_POST = _capture

        # the signature mirrors BaseHTTPRequestHandler.log_message, Any included
        def log_message(
            self,
            format: str,
            *args: Any,  # noqa: ANN401
        ) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", captured
    finally:
        server.shutdown()
        server.server_close()


_E2E_REQUESTS = [
    pytest.param(
        dict(method="GET", url="/get", params={"foo": 911, "bar": "baz"}),
        id="URL PARAMS",
    ),
    pytest.param(
        dict(method="POST", url="/post", json={"date": "2026-08-10", "msg": "hello world"}),
        id="JSON SPACES",
    ),
    pytest.param(
        dict(method="POST", url="/post", json={"msg": 'say "hi" now'}),
        id="JSON INNER QUOTES",
    ),
    pytest.param(
        dict(method="POST", url="/post", json={"path": "C:\\dir\\x"}),
        id="JSON BACKSLASHES",
    ),
    pytest.param(
        dict(method="POST", url="/post", data={"bar": "baz", "abc": "123"}),
        id="FORM",
    ),
    pytest.param(
        dict(method="POST", url="/post", json={"pct": "50% off"}),
        id="JSON PERCENT",
    ),
    pytest.param(
        dict(method="POST", url="/post", json={"name": "O'Brien"}),
        id="JSON SINGLE QUOTE",
    ),
    pytest.param(
        dict(method="POST", url="/post", params={"limit": 10}, json={"ok": True}),
        # a single-parameter query string has no & to force quoting, and zsh refuses the
        # bare ? as an unmatched glob
        id="URL SINGLE PARAM",
    ),
]

# $'...' is ANSI-C quoting, which bash, zsh and ksh expand and powershell has no answer for,
# so a body that did not decode is exercised for the sh dialect only
_SH_ONLY_REQUESTS = [
    pytest.param(
        # every byte a body can hold except NUL, which cannot survive in an argument at all
        dict(method="POST", url="/post", content=bytes(range(1, 256))),
        id="RAW BYTES",
    ),
    pytest.param(
        # the leading @ that --data and --data-binary would read as a filename
        dict(method="POST", url="/post", content=b"@\xff\xfe"),
        id="RAW BYTES LEADING AT",
    ),
]


def run_and_assert(
    base_url: str,
    captured: list[dict[str, Any]],
    request_kwargs: dict[str, Any],
    shell: str,
    script_path: pathlib.Path,
    runner_args: list[str],
    script_prelude: str = "",
    # pretty / long_options, forwarded to to_curl
    **curl_kwargs: bool,
) -> None:
    request_kwargs = dict(request_kwargs)
    request_kwargs["url"] = base_url + request_kwargs["url"]
    req = httpx.Request(**request_kwargs)
    script_path.write_text(script_prelude + to_curl(req, shell=shell, **curl_kwargs), encoding="utf-8")
    completed = subprocess.run(
        [*runner_args, str(script_path)],
        capture_output=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    debug = (completed.returncode, completed.stdout, completed.stderr)
    assert completed.returncode == 0, debug
    assert len(captured) == 1, (captured, debug)
    assert captured[0]["method"] == req.method
    assert captured[0]["path"] == req.url.raw_path.decode()
    assert captured[0]["body"] == req.read()


@pytest.mark.skipif(platform.system() == "Windows", reason="sh dialect targets POSIX shells")
@pytest.mark.parametrize("request_kwargs", _E2E_REQUESTS + _SH_ONLY_REQUESTS)
def test_sh_e2e(
    capture_server: CaptureServer,
    tmp_path: pathlib.Path,
    request_kwargs: dict[str, Any],
) -> None:
    base_url, captured = capture_server
    run_and_assert(base_url, captured, request_kwargs, SH, tmp_path / "cmd.sh", ["bash"])


# the line continuations have to survive: bash must see one command, not one per line,
# and curl must accept the url in the leading position
@pytest.mark.skipif(platform.system() == "Windows", reason="sh dialect targets POSIX shells")
@pytest.mark.parametrize("long_options", [False, True], ids=["short options", "long options"])
def test_sh_pretty_e2e(
    capture_server: CaptureServer,
    tmp_path: pathlib.Path,
    long_options: bool,
) -> None:
    base_url, captured = capture_server
    run_and_assert(
        base_url,
        captured,
        dict(method="POST", url="/post", params={"foo": 911, "bar": "baz"}, json={"msg": "hello world"}),
        SH,
        tmp_path / "cmd.sh",
        ["bash"],
        pretty=True,
        long_options=long_options,
    )


@pytest.mark.skipif(platform.system() != "Windows", reason="powershell dialect targets PowerShell on Windows")
@pytest.mark.parametrize(
    "ps_binary, script_prelude",
    [
        # Windows PowerShell 5.1, the dialect's target: the command runs as generated
        pytest.param("powershell.exe", "", id="powershell.exe"),
        # pwsh 7.2+ routes even stop-parsing-token arguments through its new argument binder;
        # this verifies the remedy documented in the README — switch the session to legacy passing
        pytest.param("pwsh", "$PSNativeCommandArgumentPassing = 'Legacy'\n", id="pwsh-legacy"),
    ],
)
@pytest.mark.parametrize("request_kwargs", _E2E_REQUESTS)
def test_powershell_e2e(
    capture_server: CaptureServer,
    tmp_path: pathlib.Path,
    ps_binary: str,
    script_prelude: str,
    request_kwargs: dict[str, Any],
) -> None:
    base_url, captured = capture_server
    run_and_assert(
        base_url,
        captured,
        request_kwargs,
        POWERSHELL,
        tmp_path / "cmd.ps1",
        [ps_binary, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"],
        script_prelude=script_prelude,
    )
