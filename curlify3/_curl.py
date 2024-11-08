import re

from asyncio import iscoroutine

from curlify3._utils import make_request_obj, make_request_obj_async

MULTIPART_FORM_DATA = re.compile(rb'form-data; name="(.[^"]+)"\r\n\r\n(.+)\r\n')
MULTIPART_FILE_DATA = re.compile(rb'form-data; name="(.[^"]+)"; filename="(.[^"]+)"')


def make_full_url(url) -> str:
    return url if not "&" in url else f"'{url}'"


def make_curl_headers(headers):
    results = []
    for header, value in headers.items():
        results.append(f"-H '{header}: {value}'")
    return " ".join(results)


def make_curl_cookies(cookies):
    if not cookies:
        return None
    if " " in cookies:
        cookies = f"'{cookies}'"
    return f"-b {cookies}"


def make_multipart_curl_args(body):
    body_parts = []
    body = body.encode() if isinstance(body, str) else body
    for matched in MULTIPART_FORM_DATA.finditer(body):
        groups = matched.groups()
        body_parts.append(f"-F '{groups[0].decode()}={groups[1].decode()}'")
    for matched in MULTIPART_FILE_DATA.finditer(body):
        groups = matched.groups()
        body_parts.append(f"-F '{groups[0].decode()}=@{groups[1].decode()}'")
    return " ".join(body_parts)


def make_curl_body(body, headers):
    if "multipart" in headers.get("content-type", ""):
        return make_multipart_curl_args(body)
    if not body:
        return ""
    return f"-d '{body}'"


def make_curl_string(method, url, headers, body, cookies):
    if "content-length" in headers:
        del headers["content-length"]
    if body and isinstance(body, (str, bytes)) and not headers.get("content-type"):
        headers["content-type"] = "plain/text"
    cli_parts = [
        f"curl",
        f"-X {method}" if method != "GET" else None,
        make_curl_cookies(cookies),
        make_curl_headers(headers),
        make_curl_body(body, headers),
        make_full_url(url),
    ]
    return " ".join([str(entity) for entity in cli_parts if entity])


def to_curl(request):
    data = make_request_obj(request)
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=data.body(),
        cookies=data.cookies,
    )


async def to_curl_async(request):
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
    )
