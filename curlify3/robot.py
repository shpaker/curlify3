"""Robot Framework keyword library rendering requests as curl commands.

    *** Settings ***
    Library    RequestsLibrary
    Library    curlify3.robot    exclude_headers=${{["user-agent"]}}

    *** Test Cases ***
    Log One Request
        ${resp}=       GET    https://httpbin.org/get
        Log As Curl    ${resp}

    Log Every Request Of A Session
        Create Session         httpbin    https://httpbin.org
        Enable Curl Logging    httpbin
        GET On Session         httpbin    /get

Needs robotframework, installed with the robot extra: pip install curlify3[robot].
The keywords take every request object to_curl() accepts, and anything carrying
one in its request attribute, such as the response RequestsLibrary returns.
"""

from typing import Any, Literal, TypeAlias

from robot.api import logger
from robot.api.deco import keyword, library
from robot.libraries.BuiltIn import BuiltIn

from curlify3._curl import SH, to_curl

__all__ = ["CurlifyLibrary", "robot"]

# the levels robot's logger.write() takes, less HTML: a command written at that level
# would be rendered as markup rather than shown as the text to copy
Level: TypeAlias = Literal["TRACE", "DEBUG", "INFO", "CONSOLE", "WARN", "ERROR"]


def _unwrap(
    request: object,
) -> object:
    # a response is what RequestsLibrary hands back, and the request it was sent for
    # rides along on it; the request types themselves carry no request attribute
    inner = getattr(request, "request", None)
    return request if inner is None else inner


class _CurlLogHook:
    # a class rather than a closure, so Disable Curl Logging can tell its own hooks
    # apart from the ones the test suite registered on the same session
    def __init__(
        self,
        library: "CurlifyLibrary",
        level: Level | None,
        options: dict[str, Any],
    ) -> None:
        self._library = library
        self._level = level
        self._options = options

    def __call__(
        self,
        response: object,
        *args: object,
        **kwargs: object,
    ) -> None:
        self._library.log_as_curl(response, level=self._level, **self._options)


@library(scope="GLOBAL", auto_keywords=False)
class CurlifyLibrary:
    """Renders HTTP requests as ready-to-run curl commands.

    The import arguments set the defaults every keyword falls back to; each keyword
    takes the same arguments to override them for one call. ``shell`` is ``sh`` or
    ``powershell``, ``include_headers`` / ``exclude_headers`` are lists of header
    names matched case-insensitively, ``level`` is the log level of the logging
    keywords.
    """

    def __init__(
        self,
        shell: str = SH,
        pretty: bool = False,
        long_options: bool = False,
        include_headers: list[str] | None = None,
        exclude_headers: list[str] | None = None,
        level: Level = "INFO",
    ) -> None:
        self._shell = shell
        self._pretty = pretty
        self._long_options = long_options
        self._include_headers = include_headers
        self._exclude_headers = exclude_headers or []
        self._level = level

    @keyword("To Curl")
    def to_curl(
        self,
        request: object,
        shell: str | None = None,
        pretty: bool | None = None,
        long_options: bool | None = None,
        include_headers: list[str] | None = None,
        exclude_headers: list[str] | None = None,
    ) -> str:
        """Returns ``request`` rendered as a curl command.

        ``request`` is a request object or a response carrying one, such as the
        response RequestsLibrary keywords return.

        | ${cmd}=    To Curl    ${resp}    pretty=True
        """
        return to_curl(
            _unwrap(request),
            shell=self._shell if shell is None else shell,
            pretty=self._pretty if pretty is None else pretty,
            long_options=self._long_options if long_options is None else long_options,
            include_headers=self._include_headers if include_headers is None else include_headers,
            exclude_headers=self._exclude_headers if exclude_headers is None else exclude_headers,
        )

    @keyword("Log As Curl")
    def log_as_curl(
        self,
        request: object,
        level: Level | None = None,
        shell: str | None = None,
        pretty: bool | None = None,
        long_options: bool | None = None,
        include_headers: list[str] | None = None,
        exclude_headers: list[str] | None = None,
    ) -> str:
        """Writes ``request`` rendered as a curl command to the log and returns it.

        Takes the arguments of `To Curl`, plus the log ``level``.

        | Log As Curl    ${resp}    level=DEBUG
        """
        command = self.to_curl(
            request,
            shell=shell,
            pretty=pretty,
            long_options=long_options,
            include_headers=include_headers,
            exclude_headers=exclude_headers,
        )
        logger.write(command, self._level if level is None else level)
        return command

    @keyword("Enable Curl Logging")
    def enable_curl_logging(
        self,
        alias: str,
        level: Level | None = None,
        shell: str | None = None,
        pretty: bool | None = None,
        long_options: bool | None = None,
        include_headers: list[str] | None = None,
        exclude_headers: list[str] | None = None,
    ) -> None:
        """Logs every request sent through the RequestsLibrary session ``alias`` as a curl command.

        Takes the arguments of `Log As Curl`. Enabling it again for the same session
        replaces the earlier arguments rather than logging each request twice.
        Requests sent with the session-less keywords (``GET``, ``POST`` ...) are not
        covered: pass their response to `Log As Curl` instead.

        | Create Session         api    https://api.example.com
        | Enable Curl Logging    api    exclude_headers=${{["user-agent"]}}
        """
        hooks = _response_hooks(alias)
        hooks[:] = [hook for hook in hooks if not isinstance(hook, _CurlLogHook)]
        hooks.append(
            _CurlLogHook(
                self,
                level,
                {
                    "shell": shell,
                    "pretty": pretty,
                    "long_options": long_options,
                    "include_headers": include_headers,
                    "exclude_headers": exclude_headers,
                },
            )
        )

    @keyword("Disable Curl Logging")
    def disable_curl_logging(
        self,
        alias: str,
    ) -> None:
        """Stops `Enable Curl Logging` for the RequestsLibrary session ``alias``."""
        hooks = _response_hooks(alias)
        hooks[:] = [hook for hook in hooks if not isinstance(hook, _CurlLogHook)]


# `Library    curlify3.robot` makes robot look for a class named like the module in it,
# on every robot version; `curlify3.robot.CurlifyLibrary` names the same class explicitly
robot = CurlifyLibrary


def _response_hooks(
    alias: str,
) -> list[Any]:
    requests_library = BuiltIn().get_library_instance("RequestsLibrary")
    # RequestsLibrary keeps its sessions in a robot ConnectionCache and exposes no
    # keyword returning one; indexing the cache does not change the current session
    cache = getattr(requests_library, "_cache", None)
    if cache is None:
        raise RuntimeError("this RequestsLibrary version keeps no session cache curlify3 can reach")
    try:
        session = cache[alias]
    except RuntimeError:
        raise RuntimeError(f"RequestsLibrary has no session with alias {alias!r}") from None
    return session.hooks.setdefault("response", [])
