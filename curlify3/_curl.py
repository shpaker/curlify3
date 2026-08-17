import re

from collections.abc import Callable, Mapping
from typing import Final, NamedTuple, TypeAlias

from curlify3._types import Body, Headers
from curlify3._utils import make_request_obj, make_request_obj_async

# a quote function also has to survive a body that did not decode
Quote: TypeAlias = Callable[[str | bytes], str]
Options: TypeAlias = Mapping[str, str]

MULTIPART_FORM_DATA: Final = re.compile(rb'form-data; name="(.[^"]+)"\r\n\r\n(.+)\r\n')
MULTIPART_FILE_DATA: Final = re.compile(rb'form-data; name="(.[^"]+)"; filename="(.[^"]+)"')

PS_QUOTE: Final = re.compile(r'(\\*)"')
PS_TRAILING_BACKSLASHES: Final = re.compile(r"\\+$")

SH: Final = "sh"
POWERSHELL: Final = "powershell"

SHORT_OPTIONS: Final[Options] = {
    "request": "-X",
    "header": "-H",
    "cookie": "-b",
    "data": "-d",
    "form": "-F",
}
LONG_OPTIONS: Final[Options] = {
    "request": "--request",
    "header": "--header",
    "cookie": "--cookie",
    "data": "--data",
    "form": "--form",
}


def quote_sh(value: str | bytes) -> str:
    return f"'{value}'"


def quote_sh_url(url: str) -> str:
    return url if "&" not in url else quote_sh(url)


def quote_sh_cookies(cookies: str) -> str:
    return quote_sh(cookies) if " " in cookies else cookies


def quote_powershell(value: str | bytes) -> str:
    # the command is emitted behind the --% stop-parsing token, so the only parser left is the
    # C runtime of curl.exe: wrap in "...", escape " as \" doubling any run of backslashes
    # directly before it, and double a trailing run so it cannot swallow the closing quote
    quoted = PS_QUOTE.sub(lambda matched: matched.group(1) * 2 + '\\"', str(value))
    quoted = PS_TRAILING_BACKSLASHES.sub(lambda matched: matched.group() * 2, quoted)
    return f'"{quoted}"'


class ShellConfig(NamedTuple):
    binary: str
    args_prefix: str
    quote: Quote
    quote_url: Callable[[str], str]
    quote_cookies: Callable[[str], str]
    # what separates arguments in pretty mode, None when the shell cannot span lines
    pretty_separator: str | None


SHELLS: Final[Mapping[str, ShellConfig]] = {
    SH: ShellConfig("curl", "", quote_sh, quote_sh_url, quote_sh_cookies, " \\\n  "),
    # --% is the stop-parsing token: Windows PowerShell 5.1 (the dialect's target) hands
    # everything after it to curl.exe verbatim (only %VAR% references expand), leaving the
    # C runtime as the single parser — 5.1's own argument binder re-quotes by counting every
    # double quote, escaped or not, and corrupts JSON payloads no matter how they are written;
    # pwsh 7.2+ binds even these arguments the new way and needs
    # $PSNativeCommandArgumentPassing = 'Legacy' in the session first (documented in README);
    # the url and cookies are always quoted to keep whitespace safe for the C runtime parser
    # pretty is impossible here: --% is effective only until the next newline and the line
    # continuation character (`) cannot extend it (about_Parsing), so a multi-line command
    # would pass the backtick to curl.exe and run the next line on its own
    POWERSHELL: ShellConfig("curl.exe", "--%", quote_powershell, quote_powershell, quote_powershell, None),
}


def make_curl_headers(headers: Headers, quote: Quote, options: Options) -> list[str]:
    option = options["header"]
    return [f"{option} {quote(f'{header}: {value}')}" for header, value in headers.items()]


def make_curl_cookies(cookies: str | None, quote_cookies: Callable[[str], str], options: Options) -> list[str]:
    if not cookies:
        return []
    return [f"{options['cookie']} {quote_cookies(cookies)}"]


def make_multipart_curl_args(body: str | bytes, quote: Quote, options: Options) -> list[str]:
    option = options["form"]
    body_parts = []
    body = body.encode() if isinstance(body, str) else body
    for matched in MULTIPART_FORM_DATA.finditer(body):
        groups = matched.groups()
        body_parts.append(f"{option} {quote(f'{groups[0].decode()}={groups[1].decode()}')}")
    for matched in MULTIPART_FILE_DATA.finditer(body):
        groups = matched.groups()
        body_parts.append(f"{option} {quote(f'{groups[0].decode()}=@{groups[1].decode()}')}")
    return body_parts


def make_curl_body(body: Body, headers: Headers, quote: Quote, options: Options) -> list[str]:
    # an absent body carries no arguments whatever the content-type claims
    if not body:
        return []
    if "multipart" in headers.get("content-type", ""):
        return make_multipart_curl_args(body, quote, options)
    return [f"{options['data']} {quote(body)}"]


def make_curl_string(
    method: str,
    url: str,
    headers: Headers,
    body: Body,
    cookies: str | None,
    http2: bool = False,
    shell: str = SH,
    pretty: bool = False,
    long_options: bool = False,
) -> str:
    if shell not in SHELLS:
        raise ValueError(f"unknown shell: {shell!r}, expected one of {sorted(SHELLS)}")
    shell_conf = SHELLS[shell]
    # non-None only when the output is asked to span lines and the shell can
    separator = shell_conf.pretty_separator if pretty else None
    if pretty and separator is None:
        raise ValueError(f"pretty output is not supported for shell: {shell!r}")
    options = LONG_OPTIONS if long_options else SHORT_OPTIONS
    if "content-length" in headers:
        del headers["content-length"]
    if body and isinstance(body, (str, bytes)) and not headers.get("content-type"):
        headers["content-type"] = "plain/text"
    args = [
        "--http2" if http2 else None,
        f"{options['request']} {method}" if method != "GET" else None,
        *make_curl_cookies(cookies, shell_conf.quote_cookies, options),
        *make_curl_headers(headers, shell_conf.quote, options),
        *make_curl_body(body, headers, shell_conf.quote, options),
    ]
    parts = [str(entity) for entity in args if entity]
    command = " ".join([part for part in (shell_conf.binary, shell_conf.args_prefix) if part])
    url = shell_conf.quote_url(url)
    if separator is not None:
        return separator.join([f"{command} {url}", *parts])
    return " ".join([command, *parts, url])


def to_curl(request: object, shell: str = SH, pretty: bool = False, long_options: bool = False) -> str:
    data = make_request_obj(request)
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=data.body(),
        cookies=data.cookies,
        http2=data.http2,
        shell=shell,
        pretty=pretty,
        long_options=long_options,
    )


async def to_curl_async(request: object, shell: str = SH, pretty: bool = False, long_options: bool = False) -> str:
    data = make_request_obj_async(request)
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=await data.body(),
        cookies=data.cookies,
        http2=data.http2,
        shell=shell,
        pretty=pretty,
        long_options=long_options,
    )
