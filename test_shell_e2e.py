"""End-to-end checks: the generated command is executed by a real shell and a local
HTTP server verifies that the request arrives byte-for-byte intact.

The PowerShell tests run only on Windows (powershell.exe 5.1, the dialect target);
the sh tests run everywhere else via bash. CI covers both via ubuntu and windows jobs.
"""

import platform
import subprocess
import threading

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
import pytest

from curlify3 import POWERSHELL, SH, to_curl

SUBPROCESS_TIMEOUT = 120


@pytest.fixture
def capture_server():
    captured = []

    class CaptureHandler(BaseHTTPRequestHandler):
        def _capture(self):
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

        def log_message(self, *args):
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
]

# sh output does not survive a single quote in the body (pre-existing quoting gap),
# so this payload is exercised for the powershell dialect only
_POWERSHELL_ONLY_REQUESTS = [
    pytest.param(
        dict(method="POST", url="/post", json={"name": "O'Brien"}),
        id="JSON SINGLE QUOTE",
    ),
]


def run_and_assert(base_url, captured, request_kwargs, shell, script_path, runner_args):
    request_kwargs = dict(request_kwargs)
    request_kwargs["url"] = base_url + request_kwargs["url"]
    req = httpx.Request(**request_kwargs)
    script_path.write_text(to_curl(req, shell=shell), encoding="utf-8")
    completed = subprocess.run(
        runner_args + [str(script_path)],
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
@pytest.mark.parametrize("request_kwargs", _E2E_REQUESTS)
def test_sh_e2e(capture_server, tmp_path, request_kwargs: dict[str, Any]) -> None:
    base_url, captured = capture_server
    run_and_assert(base_url, captured, request_kwargs, SH, tmp_path / "cmd.sh", ["bash"])


@pytest.mark.skipif(platform.system() != "Windows", reason="powershell dialect targets PowerShell on Windows")
@pytest.mark.parametrize("ps_binary", ["powershell.exe", "pwsh"])
@pytest.mark.parametrize("request_kwargs", _E2E_REQUESTS + _POWERSHELL_ONLY_REQUESTS)
def test_powershell_e2e(capture_server, tmp_path, ps_binary: str, request_kwargs: dict[str, Any]) -> None:
    # both Windows PowerShell 5.1 and pwsh 7.3+, whose native argument passing differs —
    # the --% stop-parsing token makes the generated command behave identically in both
    base_url, captured = capture_server
    run_and_assert(
        base_url,
        captured,
        request_kwargs,
        POWERSHELL,
        tmp_path / "cmd.ps1",
        [ps_binary, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"],
    )
