# API reference

Everything below is importable from `curlify3`. Modules and names starting with an underscore, the adapter classes included, are internal.

```{py:module} curlify3
```

## Functions

````{py:function} to_curl(request, shell="sh", pretty=False, long_options=False, include_headers=None, exclude_headers=(), mask_headers=()) -> str

Render a request object as a `curl` command.

Accepts the synchronous client-side request types — `requests.PreparedRequest`, `niquests.PreparedRequest`, `httpx.Request`, `httpx2.Request`, `urllib.request.Request`, `tornado.httpclient.HTTPRequest` — and the server-side requests whose body the framework has already buffered: `django.http.HttpRequest`, `werkzeug.wrappers.Request` / `flask.Request`, `tornado.httputil.HTTPServerRequest`. See [Supported request objects](adapters.md).

:param request: the request object to render.
:param shell: the output dialect, {py:data}`SH` (POSIX shells, the default) or {py:data}`POWERSHELL` (Windows PowerShell 5.1). See [Windows PowerShell](guide/powershell.md).
:type shell: str
:param pretty: put every option on its own line.
:type pretty: bool
:param long_options: spell the options out, `--header` instead of `-H`.
:type long_options: bool
:param include_headers: render only the named headers; `None` renders all of them.
:type include_headers: ~collections.abc.Iterable[str] | None
:param exclude_headers: leave the named headers out, after `include_headers`.
:type exclude_headers: ~collections.abc.Iterable[str]
:param mask_headers: keep the named headers but print `***` in place of their values, after the filters. See [Filtering and masking headers](guide/headers.md).
:type mask_headers: ~collections.abc.Iterable[str]
:returns: the command.
:rtype: str
:raises UnsupportedRequestError: no adapter accepts the request.
:raises ValueError: see [Errors](#errors).
:raises TypeError: a header option is a `str` rather than an iterable of names, or holds a name that is not a `str`.
````

````{py:function} to_curl_async(request, shell="sh", pretty=False, long_options=False, include_headers=None, exclude_headers=(), mask_headers=()) -> str
:async:

Render a request object as a `curl` command, awaiting the body.

Accepts the request types whose body has to be awaited — `aiohttp.web.Request`, `aiohttp.ClientRequest`, `starlette.requests.Request` (FastAPI) — and `httpx.Request` / `httpx2.Request`, whose body may be an async stream. The parameters, the result and the errors are those of {py:func}`to_curl`.
````

## Constants

```{py:data} SH
:type: str
:value: '"sh"'

The POSIX shell dialect, the default: `bash`, `zsh`, `ksh` and the like.
```

```{py:data} POWERSHELL
:type: str
:value: '"powershell"'

The Windows PowerShell 5.1 dialect: `curl.exe --% …`.
```

```{py:data} SENSITIVE_HEADERS
:type: frozenset[str]

The headers that carry credentials in the common case, for `mask_headers=SENSITIVE_HEADERS`: `authorization`, `proxy-authorization`, `cookie`, `x-api-key`, `x-auth-token` and `x-csrf-token`.
```

```{py:data} __version__
:type: str

The installed version.
```

## Exceptions

```{py:exception} UnsupportedRequestError
Bases: {py:class}`TypeError`, {py:class}`ValueError`

Raised by {py:func}`to_curl` and {py:func}`to_curl_async` when no adapter accepts the request object. The message starts with `unknown request object`, names the type that was passed, and says when the other entrypoint accepts it:

    unknown request object: starlette.requests.Request, it is accepted by to_curl_async(), use that instead

An unsupported type is a type error, hence the `TypeError` base. The `ValueError` base keeps `except ValueError` working, which is what releases before 0.15 raised.
```

## Errors

Both functions raise `ValueError` when:

- `shell` is not one of {py:data}`SH` and {py:data}`POWERSHELL`;
- `pretty=True` is combined with `shell="powershell"`;
- with `shell="powershell"`, the body or a multipart field value is not valid UTF-8, or any value contains a line break;
- the body or a multipart field value contains a NUL byte.

They raise `TypeError` when `include_headers`, `exclude_headers` or `mask_headers` is a `str` rather than an iterable of names, or holds a name that is not a `str`, and {py:class}`UnsupportedRequestError` when no adapter accepts the request object.

A body that cannot be read without consuming it — a stream, a drained form — is not an error: the command carries the rest of the request and no `-d`.
