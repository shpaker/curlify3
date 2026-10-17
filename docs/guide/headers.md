# Filtering and masking headers

A command copied into a log or a bug report rarely needs every header a client sends, and must not carry the credentials. Three per-call options control what the headers look like in the command; none of them changes the request object.

## Filtering

`exclude_headers` leaves the named headers out, `include_headers` renders only the named ones. Names match case-insensitively.

```python
import requests
from curlify3 import to_curl

req = requests.Session().prepare_request(
    requests.Request(
        "POST",
        "https://httpbin.org/post",
        headers={"Authorization": "Bearer t0ken"},
        json={"date": "2026-08-10"},
    )
)

print(to_curl(req))
# curl -X POST -H 'user-agent: python-requests/2.34.2' -H 'accept-encoding: gzip, deflate' -H 'accept: */*' -H 'connection: keep-alive' -H 'authorization: Bearer t0ken' -H 'content-type: application/json' -d '{"date": "2026-08-10"}' https://httpbin.org/post

print(to_curl(req, exclude_headers=["user-agent", "accept-encoding", "accept", "connection"]))
# curl -X POST -H 'authorization: Bearer t0ken' -H 'content-type: application/json' -d '{"date": "2026-08-10"}' https://httpbin.org/post

print(to_curl(req, include_headers=["content-type"]))
# curl -X POST -H 'content-type: application/json' -d '{"date": "2026-08-10"}' https://httpbin.org/post
```

- The two combine: `include_headers` narrows first, `exclude_headers` subtracts from what is left.
- `include_headers=None`, the default, renders every header; `include_headers=[]` renders none.
- `Cookie` counts as a header, so a filter that drops it drops `-b` as well.
- The filter only decides what is printed. Leaving out `content-type` hides its `-H`, but a multipart body is still rendered as `-F` parts.

## Masking

`mask_headers` keeps the named headers in the command but prints `***` in place of their values. The command still shows what the request carried; paste the real value back in to replay it. {py:data}`~curlify3.SENSITIVE_HEADERS` holds the usual credential-carrying names: `authorization`, `proxy-authorization`, `cookie`, `x-api-key`, `x-auth-token` and `x-csrf-token`.

```python
import requests
from curlify3 import SENSITIVE_HEADERS, to_curl

req = requests.Request(
    "GET",
    "https://httpbin.org/get",
    headers={"Authorization": "Bearer t0ken", "X-Api-Key": "k3y"},
    cookies={"sid": "s3cret", "theme": "dark"},
).prepare()

print(to_curl(req, mask_headers=SENSITIVE_HEADERS))
# curl -b 'sid=***; theme=***' -H 'authorization: Bearer ***' -H 'x-api-key: ***' https://httpbin.org/get
```

- `authorization` and `proxy-authorization` keep their scheme: `Basic ***`, `Bearer ***`.
- A masked `cookie` keeps the name of each cookie in `-b`: which cookies a request carried is often the question.
- An empty value has nothing to hide and stays `-H 'name;'`.
- Masking applies after filtering: the filters decide which headers are printed, `mask_headers` masks what is left.
- Masking is opt-in. The default masks nothing, so a command copied from a debugger runs as is.
- Only headers are covered. A secret in the query string or in the body is printed as it is.

## Validation

Each option takes an iterable of `str` names. A bare string such as `exclude_headers="accept"` raises `TypeError` rather than being read one character at a time, and so does a name that is not a `str`.
