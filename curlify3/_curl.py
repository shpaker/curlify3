import re

from asyncio import iscoroutine

from curlify3._utils import make_request_obj, make_request_obj_async

MULTIPART_FORM_DATA = re.compile(rb'form-data; name="(.[^"]+)"\r\n\r\n(.+)\r\n')
MULTIPART_FILE_DATA = re.compile(rb'form-data; name="(.[^"]+)"; filename="(.[^"]+)"')

SH = "sh"
POWERSHELL = "powershell"


def quote_sh(value):
    return f"'{value}'"


def quote_powershell(value):
    # inside PowerShell single-quoted literals a quote is escaped by doubling it;
    # double quotes need \" to survive argument passing to a native executable (curl.exe)
    escaped = str(value).replace("'", "''").replace('"', '\\"')
    return f"'{escaped}'"


SHELLS = {
    SH: ("curl", quote_sh),
    POWERSHELL: ("curl.exe", quote_powershell),
}


def make_full_url(url, quote):
    return url if not "&" in url else quote(url)


def make_curl_headers(headers, quote):
    results = []
    for header, value in headers.items():
        results.append(f"-H {quote(f'{header}: {value}')}")
    return " ".join(results)


def make_curl_cookies(cookies, quote):
    if not cookies:
        return None
    if " " in cookies:
        cookies = quote(cookies)
    return f"-b {cookies}"


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
    binary, quote = SHELLS[shell]
    if "content-length" in headers:
        del headers["content-length"]
    if body and isinstance(body, (str, bytes)) and not headers.get("content-type"):
        headers["content-type"] = "plain/text"
    cli_parts = [
        binary,
        "--http2" if http2 else None,
        f"-X {method}" if method != "GET" else None,
        make_curl_cookies(cookies, quote),
        make_curl_headers(headers, quote),
        make_curl_body(body, headers, quote),
        make_full_url(url, quote),
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
