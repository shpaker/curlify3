# Payload handling

| Payload | Rendered as |
| --- | --- |
| Plain text | `-d 'text'` |
| JSON | `-d '{"k":"v"}'` with `content-type: application/json` |
| Form-encoded | `-d 'k=v&k2=v2'` with `content-type: application/x-www-form-urlencoded` |
| Multipart form | `-F 'field=value' -F 'file=@name'`, in the order the body carries the parts |
| Other multipart | `-d` with the body as it is: `multipart/related`, `multipart/mixed` |
| Not valid UTF-8 | `--data-raw $'\xff\xfe'` |
| Starts with `@` or `<` | `--data-raw '@name'`, `--form-string 'field=@name'` |
| No body | no `-d` |

## Text, JSON and forms

A body that decodes as UTF-8 goes out with `-d`, quoted for the shell:

```python
import httpx
from curlify3 import to_curl

print(to_curl(httpx.Request("POST", "https://example.com/form", data={"a": "1", "b": "two words"})))
# curl -X POST -H 'host: example.com' -H 'content-type: application/x-www-form-urlencoded' -d 'a=1&b=two+words' https://example.com/form
```

The body is rendered as the bytes the request carries — the JSON a client serialised, the form it encoded — not re-encoded from the data you passed in. A body sent without a `Content-Type` gets `content-type: text/plain`, so `curl` does not add a form-encoded one of its own. `urllib.request` and `tornado` (for a POST) send `application/x-www-form-urlencoded` in that case, and the command carries that instead.

## Multipart forms

A `multipart/form-data` body is taken apart on its boundary and every part is rendered as an `-F`, so `curl` builds the same form:

```python
import httpx
from curlify3 import to_curl

req = httpx.Request("POST", "https://example.com/upload", data={"title": "x"}, files={"file": ("report.pdf", b"%PDF")})
print(to_curl(req))
# curl -X POST -H 'host: example.com' -H 'content-type: multipart/form-data' -F 'title=x' -F 'file=@report.pdf' https://example.com/upload
```

- A file part is spelled `-F 'name=@filename'`: run the command next to a file of that name and `curl` sends it. The content of the file is not in the command.
- The `boundary` parameter is left out of the `content-type` header. `-F` makes `curl` pick a boundary of its own and append it; one left in would send two.
- A part with `filename=""`, which a browser sends for a file input left empty, is rendered as `-F 'name=;filename=""'`.
- A field value `-F` would parse — one containing `;` or starting with `"`, `@` or `<` — goes through `--form-string`, which takes it literally.
- A filename holding `;`, `,`, `"` or `\` is written as a quoted string, `-F 'f=@"a;b.txt"'`, which `curl` does not cut short.
- Part names, values and filenames that are not valid UTF-8 are written in ANSI-C quoting, `-F $'blob=caf\xe9'`.
- A multipart content-type without a `boundary` leaves nothing to take the body apart with, and the command carries no body.

Only `multipart/form-data` is what `-F` builds. `multipart/related`, `multipart/mixed` and the other subtypes carry no field names; their body goes out with `-d` as it is, together with the boundary it was written with.

## Binary bodies

A body that does not decode as UTF-8 is rendered as an ANSI-C quoted literal. Only the bytes that have to be escaped are, so a mis-encoded text body stays readable:

```python
print(to_curl(httpx.Request("POST", "https://example.com/", content=b"caf\xe9")))
# curl -X POST -H 'host: example.com' -H 'content-type: text/plain' --data-raw $'caf\xe9' https://example.com/
```

- `$'…'` is understood by `bash`, `zsh` and `ksh`, but it is **not** POSIX: `dash` and BusyBox `ash` pass `$\xff\xfe` through literally. The dialect is named `sh`, but a binary body needs one of the former.
- `--data-raw` rather than `-d`: both `-d` and `--data-binary` read a leading `@` as a filename, and `@` is an ordinary byte in a binary payload.
- With `shell="powershell"` such a body raises `ValueError`: raw bytes have no spelling behind `--%`.

## Values curl would read as a file

`curl` reads a leading `@` in a `-d` value, and a leading `@` or `<` in an `-F` value, as the name of a local file to send. A body or field that genuinely starts with one is rendered with the option that takes the value literally:

```python
print(to_curl(httpx.Request("POST", "https://example.com/", content="@/etc/passwd")))
# curl -X POST -H 'host: example.com' -H 'content-type: text/plain' --data-raw '@/etc/passwd' https://example.com/
```

See [Quoting and untrusted values](security.md) for why this matters on the server side.

## Values no command can carry

A command-line argument ends at a NUL byte, so no quoting can carry one. A body or a multipart field value containing a NUL raises `ValueError`: a command that ran and silently sent a truncated body would be worse than none.

## Methods

| Request | Rendered as |
| --- | --- |
| GET without a body | no option, `curl`'s default |
| GET with a body | `-X GET`: a body alone makes `curl` send POST |
| HEAD | `-I` / `--head`: `-X HEAD` leaves `curl` waiting for a response body that never comes |
| any other | `-X METHOD` |

## Urls

The url is quoted whenever it holds a character a shell would act on — including the `?` of a single-parameter query string, which `zsh` rejects as an unmatched glob. A url containing `[`, `]`, `{` or `}` gets `-g` / `--globoff`, since `curl` would otherwise expand them into several requests:

```python
print(to_curl(httpx.Request("GET", "https://example.com/items?ids[]=1&ids[]=2")))
# curl -g -H 'host: example.com' 'https://example.com/items?ids[]=1&ids[]=2'
```

## Headers and cookies

| Header | Rendered as |
| --- | --- |
| ordinary | `-H 'name: value'`, name lowercased |
| repeated | one `-H`, values joined with `, ` |
| empty value | `-H 'name;'`: `curl` drops `-H 'name: '` without sending it |
| `Cookie` | `-b 'k=v; k2=v2'`, repeated `Cookie` headers joined with `; ` |
| `Cookie` without an `=` | `-H 'cookie: …'`: `-b` would read it as the name of a cookie file |
| `Content-Length` | left out, `curl` computes it |
