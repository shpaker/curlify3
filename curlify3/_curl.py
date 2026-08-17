import re

from asyncio import iscoroutine
from typing import Callable, NamedTuple

from curlify3._utils import make_request_obj, make_request_obj_async

MULTIPART_FORM_DATA = re.compile(rb'form-data; name="(.[^"]+)"\r\n\r\n(.+)\r\n')
MULTIPART_FILE_DATA = re.compile(rb'form-data; name="(.[^"]+)"; filename="(.[^"]+)"')

PS_QUOTE = re.compile(r'(\\*)"')
PS_TRAILING_BACKSLASHES = re.compile(r"\\+$")
PS_WHITESPACE = re.compile(r"\s")

SH = "sh"
POWERSHELL = "powershell"


def quote_sh(value):
    return f"'{value}'"


def quote_sh_url(url):
    return url if not "&" in url else quote_sh(url)


def quote_sh_cookies(cookies):
    return quote_sh(cookies) if " " in cookies else cookies


def quote_powershell(value):
    # targets Windows PowerShell 5.1 / pwsh <= 7.2, which pass arguments to native executables
    # (curl.exe) unescaped, so the value must survive two parsers: MSVCRT command-line rules
    # first — a double quote becomes \" and any run of backslashes directly before it doubles;
    # a value with whitespace gets wrapped in "..." on the native command line, so a trailing
    # backslash run doubles too — then a PowerShell single-quoted literal, where ' doubles
    value = PS_QUOTE.sub(lambda matched: matched.group(1) * 2 + '\\"', str(value))
    if PS_WHITESPACE.search(value):
        value = PS_TRAILING_BACKSLASHES.sub(lambda matched: matched.group() * 2, value)
    return "'" + value.replace("'", "''") + "'"


class ShellConfig(NamedTuple):
    binary: str
    quote: Callable
    quote_url: Callable
    quote_cookies: Callable


SHELLS = {
    SH: ShellConfig("curl", quote_sh, quote_sh_url, quote_sh_cookies),
    # url and cookies are always quoted: unquoted `,` `;` `$` `(` are PowerShell metacharacters
    POWERSHELL: ShellConfig("curl.exe", quote_powershell, quote_powershell, quote_powershell),
}


def make_curl_headers(headers, quote):
    results = []
    for header, value in headers.items():
        results.append(f"-H {quote(f'{header}: {value}')}")
    return " ".join(results)


def make_curl_cookies(cookies, quote_cookies):
    if not cookies:
        return None
    return f"-b {quote_cookies(cookies)}"


def make_multipart_curl_args(body, quote):
    body_parts = []
    body = body.encode() if isinstance(body, str) else body
    for matched in MULTIPART_FORM_DATA.finditer(body):
        groups = matched.groups()
        body_parts.append(f"-F {quote(f'{groups[0].decode()}={groups[1].decode()}')}")
    for matched in MULTIPART_FILE_DATA.finditer(body):
        groups = matched.groups()
        body_parts.append(f"-F {quote(f'{groups[0].decode()}=@{groups[1].decode()}')}")
    return " ".join(body_parts)


def make_curl_body(body, headers, quote):
    if "multipart" in headers.get("content-type", ""):
        return make_multipart_curl_args(body, quote)
    if not body:
        return ""
    return f"-d {quote(body)}"


def make_curl_string(method, url, headers, body, cookies, http2=False, shell=SH):
    if shell not in SHELLS:
        raise ValueError(f"unknown shell: {shell!r}, expected one of {sorted(SHELLS)}")
    shell_conf = SHELLS[shell]
    if "content-length" in headers:
        del headers["content-length"]
    if body and isinstance(body, (str, bytes)) and not headers.get("content-type"):
        headers["content-type"] = "plain/text"
    cli_parts = [
        shell_conf.binary,
        "--http2" if http2 else None,
        f"-X {method}" if method != "GET" else None,
        make_curl_cookies(cookies, shell_conf.quote_cookies),
        make_curl_headers(headers, shell_conf.quote),
        make_curl_body(body, headers, shell_conf.quote),
        shell_conf.quote_url(url),
    ]
    return " ".join([str(entity) for entity in cli_parts if entity])


def to_curl(request, shell=SH):
    data = make_request_obj(request)
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=data.body(),
        cookies=data.cookies,
        http2=getattr(data, "http2", False),
        shell=shell,
    )


async def to_curl_async(request, shell=SH):
    data = make_request_obj_async(request)
    body = data.body()
    if iscoroutine(body):
        body = await body
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=body,
        cookies=data.cookies,
        http2=getattr(data, "http2", False),
        shell=shell,
    )
