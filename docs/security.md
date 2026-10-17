# Quoting and untrusted values

On the server side, every value in a rendered command was chosen by whoever sent the request: the path, the query, the headers, the cookies, the body. A command written to a log and later pasted into a terminal runs in the reader's shell, with the reader's files at hand. `curlify3` renders such a command so that it sends the request it was rendered from and does nothing else.

## Every value is quoted

Every value is quoted for the target shell, so it stays data and never becomes part of the command:

```python
# an incoming request whose path and cookie were chosen by the caller
print(await to_curl_async(request))
# curl -b 'n=O'\''Brien' -H 'host: example.com' 'http://example.com/x;id'
```

Rendered bare, that path would run `id`. With `shell="sh"`, values go in single quotes, and a single quote inside is written as `'\''`. The url and the cookie header are left bare when every character in them is in the safe set `shlex.quote()` uses, which keeps the common command short. With `shell="powershell"`, values go in double quotes behind `--%`, see [Windows PowerShell](guide/powershell.md).

## Nothing reads a local file

Several `curl` options read a local file when their value takes a certain shape. A value from the request never takes that shape in the command:

| Value | What `curl` would do | Rendered as |
| --- | --- | --- |
| body starting with `@` | send the named file as the body | `--data-raw` |
| field value starting with `@` or `<` | send the named file as the field | `--form-string` |
| field value with `;headers=@file` | load the part headers from the file | `--form-string` |
| field value with `;type=` or `;filename=` | change the part, cut the value short | `--form-string` |
| `Cookie` header without an `=` | read the named cookie jar and send its cookies | `-H 'cookie: …'` |
| filename with `;` or `,` | cut the name short, or read a list of files | `-F 'f=@"a;b.txt"'` |

A file *part* keeps `-F 'field=@filename'`: there the `@` is the point, and the command sends the file of that name from the directory it runs in.

## Nothing runs but curl

- With `shell="powershell"`, a value holding a line break raises `ValueError`. `--%` ends at the line break, and the next line would run as a PowerShell command.
- A url holding `[`, `]`, `{` or `}` gets `-g`, so `curl` does not expand it into several requests.
- A value containing a NUL byte raises `ValueError`, since it would cut the argument short.

These are verified end to end: the test suite runs the rendered commands in `bash` — and on Windows CI in `powershell.exe` 5.1 and `pwsh` — against a local server, and checks that the request arrives byte for byte. The file-reference cases put a secret file next to the command and check that it is not sent.

## Secrets in the command

The command reproduces the request, credentials included, unless asked otherwise. Before a command goes to a log, mask the credentials with `mask_headers` — {py:data}`~curlify3.SENSITIVE_HEADERS` covers the usual ones — or leave headers out with `exclude_headers`; see [Filtering and masking headers](guide/headers.md). Secrets in the url or in the body are printed as they are.

## Limits

- `%NAME%` references in a value are still expanded by PowerShell.
- `$'…'` quoting of a binary body needs `bash`, `zsh` or `ksh`; `dash` and BusyBox `ash` do not expand it.

## Reporting a vulnerability

If a rendered command does something other than send the request it was rendered from, please report it privately, as described in [SECURITY.md](https://github.com/shpaker/curlify3/blob/main/SECURITY.md).
