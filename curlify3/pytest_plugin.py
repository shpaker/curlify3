"""pytest plugin: the curl commands of the HTTP requests a failing test sent.

Load it from the root conftest.py (or with ``-p curlify3.pytest_plugin``):

    pytest_plugins = ["curlify3.pytest_plugin"]

then turn it on for the whole run with ``--curl-on-failure`` or the
``curl_on_failure`` ini option, or for a single test by requesting the
``curl_requests`` fixture, which also hands back the rendered commands:

    def test_create_order(client, curl_requests):
        resp = client.post("/orders", json={"qty": 2})
        assert resp.status_code == 201, curl_requests[-1]

A failing test then carries a "Captured curl" section with one command per
request, numbered in the order they were sent and labelled with the status of
the response. Requests are recorded at the clients' ``send``: httpx and httpx2
(sync and async, which covers the starlette / FastAPI TestClient), requests and
niquests (sync and async).
"""

import functools

from collections.abc import Callable, Generator, Iterator
from contextlib import suppress
from typing import Any

import pytest

from curlify3._curl import to_curl, to_curl_async

_DEFAULT_MAX_REQUESTS = 20

# a client class, whether its send() is a coroutine, and whether the request
# has to be rendered with to_curl_async() (the httpx request body may be an
# async stream, which only aread() can take)
_SendTarget = tuple[type[Any], bool, bool]


def _send_targets() -> list[_SendTarget]:
    targets: list[_SendTarget] = []
    with suppress(ImportError):
        import httpx

        targets += [(httpx.Client, False, False), (httpx.AsyncClient, True, True)]
    with suppress(ImportError):
        import httpx2

        targets += [(httpx2.Client, False, False), (httpx2.AsyncClient, True, True)]
    with suppress(ImportError):
        import requests

        targets.append((requests.Session, False, False))
    with suppress(ImportError):
        import niquests

        # the async session sends the same PreparedRequest as the sync one,
        # which only the sync adapter takes
        targets += [(niquests.Session, False, False), (niquests.AsyncSession, True, False)]
    return targets


def _status(
    response: Any,  # noqa: ANN401
) -> str | None:
    # a lazy (multiplexed) niquests response has not arrived yet, and reading
    # its status would block on it inside send()
    if getattr(response, "lazy", False):
        return None
    status = getattr(response, "status_code", None)
    return None if status is None else str(status)


class CurlCapture:
    """The requests sent while a test runs, rendered as curl commands at send time.

    The body is rendered before the client sends it: a streaming body may be
    gone by the time the test fails.
    """

    def __init__(
        self,
        exclude_headers: list[str],
        mask_headers: list[str],
    ) -> None:
        self.commands: list[str] = []
        self._outcomes: list[str | None] = []
        self._exclude_headers = exclude_headers
        self._mask_headers = mask_headers
        self._restore: list[Callable[[], None]] = []

    def _record(
        self,
        command: str,
    ) -> int:
        self.commands.append(command)
        self._outcomes.append(None)
        return len(self.commands) - 1

    def record(
        self,
        request: object,
    ) -> int:
        # a request the plugin cannot render must not fail the test that sent it
        try:
            command = to_curl(
                request,
                exclude_headers=self._exclude_headers,
                mask_headers=self._mask_headers,
            )
        except Exception as exc:
            command = f"# not rendered: {exc!r}"
        return self._record(command)

    async def record_async(
        self,
        request: object,
    ) -> int:
        try:
            command = await to_curl_async(
                request,
                exclude_headers=self._exclude_headers,
                mask_headers=self._mask_headers,
            )
        except Exception as exc:
            command = f"# not rendered: {exc!r}"
        return self._record(command)

    def settle(
        self,
        index: int,
        outcome: str | None,
    ) -> None:
        self._outcomes[index] = outcome

    def _wrap_send(
        self,
        send: Callable[..., Any],
    ) -> Callable[..., Any]:
        @functools.wraps(send)
        def wrapper(
            client: object,
            request: object,
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> Any:  # noqa: ANN401
            index = self.record(request)
            try:
                response = send(client, request, *args, **kwargs)
            except BaseException as exc:
                self.settle(index, type(exc).__name__)
                raise
            self.settle(index, _status(response))
            return response

        return wrapper

    def _wrap_send_async(
        self,
        send: Callable[..., Any],
        render_async: bool,
    ) -> Callable[..., Any]:
        @functools.wraps(send)
        async def wrapper(
            client: object,
            request: object,
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> Any:  # noqa: ANN401
            index = await self.record_async(request) if render_async else self.record(request)
            try:
                response = await send(client, request, *args, **kwargs)
            except BaseException as exc:
                self.settle(index, type(exc).__name__)
                raise
            self.settle(index, _status(response))
            return response

        return wrapper

    def start(
        self,
    ) -> None:
        for cls, is_async, render_async in _send_targets():
            send = cls.__dict__["send"]
            wrapped = self._wrap_send_async(send, render_async) if is_async else self._wrap_send(send)
            cls.send = wrapped
            self._restore.append(functools.partial(setattr, cls, "send", send))

    def stop(
        self,
    ) -> None:
        while self._restore:
            self._restore.pop()()

    def report(
        self,
        max_requests: int,
    ) -> str:
        """The section text: every request under a `# [n] status` comment, the last max_requests of them."""
        first = max(len(self.commands) - max_requests, 0) if max_requests > 0 else 0
        lines = [f"# ... {first} earlier requests omitted"] if first else []
        for index in range(first, len(self.commands)):
            outcome = self._outcomes[index]
            lines.append(f"# [{index + 1}]" if outcome is None else f"# [{index + 1}] {outcome}")
            lines.append(self.commands[index])
        return "\n".join(lines)


_CAPTURE_KEY = pytest.StashKey[CurlCapture]()
_MAX_REQUESTS_KEY = pytest.StashKey[int]()


def pytest_addoption(
    parser: pytest.Parser,
) -> None:
    group = parser.getgroup("curlify3")
    group.addoption(
        "--curl-on-failure",
        action="store_true",
        default=False,
        help="attach the curl commands of the HTTP requests a failing test sent to its report",
    )
    parser.addini(
        "curl_on_failure",
        type="bool",
        default=False,
        help="the same as --curl-on-failure",
    )
    parser.addini(
        "curl_exclude_headers",
        type="linelist",
        default=[],
        help="header names left out of the captured curl commands",
    )
    parser.addini(
        "curl_mask_headers",
        type="linelist",
        default=[],
        help="header names kept in the captured curl commands with *** in place of their values",
    )
    parser.addini(
        "curl_max_requests",
        default=str(_DEFAULT_MAX_REQUESTS),
        help=f"how many of the last requests a failure report lists, 0 for all (default {_DEFAULT_MAX_REQUESTS})",
    )


def pytest_configure(
    config: pytest.Config,
) -> None:
    # checked up front: a typo found while reporting a failure would turn it
    # into an internal error
    value = config.getini("curl_max_requests")
    try:
        max_requests = int(value)
    except ValueError:
        max_requests = -1
    if max_requests < 0:
        raise pytest.UsageError(f"curl_max_requests must be a non-negative integer, got {value!r}")
    config.stash[_MAX_REQUESTS_KEY] = max_requests


def _start_capture(
    item: pytest.Item,
) -> CurlCapture:
    capture = CurlCapture(
        exclude_headers=item.config.getini("curl_exclude_headers"),
        mask_headers=item.config.getini("curl_mask_headers"),
    )
    item.stash[_CAPTURE_KEY] = capture
    capture.start()
    return capture


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(
    item: pytest.Item,
) -> Iterator[None]:
    config = item.config
    capture = _start_capture(item) if config.getoption("curl_on_failure") or config.getini("curl_on_failure") else None
    try:
        yield
    finally:
        if capture is not None:
            capture.stop()
        # the item outlives its run, the captured bodies need not
        with suppress(KeyError):
            del item.stash[_CAPTURE_KEY]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, Any, None]:
    outcome = yield
    report: pytest.TestReport = outcome.get_result()
    capture = item.stash.get(_CAPTURE_KEY, None)
    if capture is None or not report.failed or not capture.commands:
        return
    report.sections.append((f"Captured curl {report.when}", capture.report(item.config.stash[_MAX_REQUESTS_KEY])))


@pytest.fixture
def curl_requests(
    request: pytest.FixtureRequest,
) -> Iterator[list[str]]:
    """The curl commands of the requests the test sent, in the order they were sent.

    Requesting the fixture turns the capture on for this test, so a failure
    report carries them as well.
    """
    capture = request.node.stash.get(_CAPTURE_KEY, None)
    if capture is not None:
        yield capture.commands
        return
    capture = _start_capture(request.node)
    try:
        yield capture.commands
    finally:
        capture.stop()
