# Changelog

## Unreleased

### Added
- A Robot Framework keyword library, imported as `Library    curlify3.robot` and installed with the `robot` extra (`pip install curlify3[robot]`). `To Curl` returns the command, `Log As Curl` writes it to the log, `Enable Curl Logging` / `Disable Curl Logging` log every request sent through a RequestsLibrary session. The keywords take the response RequestsLibrary returns as well as the request objects `to_curl()` accepts, and the `to_curl()` options as arguments; given at import, they become the library-wide defaults. The core package still has no runtime dependencies: only `curlify3.robot` imports Robot Framework.

### Changed
- An unsupported request object is reported by type, with the fix when there is one ([#33](https://github.com/shpaker/curlify3/issues/33)). The bare `unknown request object` now carries the `module.qualname` of what was passed, and when the other entrypoint accepts the object — a starlette, FastAPI or aiohttp request handed to the sync `to_curl()`, or a `requests.PreparedRequest` to `to_curl_async()` — the message says to use that one instead. The exception is the new `curlify3.UnsupportedRequestError`, a subclass of both `TypeError` and `ValueError`: an unsupported type is a type error, and `except ValueError` written against earlier releases keeps catching it. The message still starts with `unknown request object`.
### Added
- `mask_headers` on `to_curl()` and `to_curl_async()` keeps the named headers in the command but prints `***` in place of their values, so a rendered command can go to a log without the credentials it carried ([#35](https://github.com/shpaker/curlify3/issues/35)). `authorization` and `proxy-authorization` keep the auth scheme (`Bearer ***`), and a masked `cookie` keeps the name of each cookie in `-b` (`-b 'sid=***; theme=***'`). Names match case-insensitively; the include/exclude filters decide what is printed and masking applies to what is left. The new `SENSITIVE_HEADERS` constant holds the usual credential-carrying names and is what the FastAPI middleware example in the README now passes, together with an `exclude_headers` list that drops the headers every client sends. Opt-in: the default masks nothing, so existing output does not change. Query-string and body secrets are not covered.

### Fixed
- `shell="powershell"` no longer renders a value holding a line break ([#45](https://github.com/shpaker/curlify3/issues/45)). `--%` is effective only until the end of the line, so the rest of a multi-line body, header or field value ran as PowerShell commands of its own — reachable from the wire through the server-side adapters, where a body such as `x"` + newline + `Get-Date; #` is the caller's to choose. Such a value now raises `ValueError`, like raw bytes already did.
- A multipart field value that `-F` would parse is rendered with `--form-string` ([#45](https://github.com/shpaker/curlify3/issues/45)). A `;` started an attribute — `;headers=@file` loaded the part headers from a **local file**, `;type=` and `;filename=` changed the part and cut the value short — and a leading `"` opened a quoted string whose tail was dropped. Only a leading `@` or `<` was handled before.
- A multipart filename holding `;`, `,`, `"` or `\` is written as a quoted string, `-F 'f=@"a;b.txt"'` ([#45](https://github.com/shpaker/curlify3/issues/45)). `-F` cut a bare one at the `;` or read the `,` as a list of files, so the command sent another file or failed.
- A `Cookie` header without an `=` is rendered as `-H 'cookie: …'` ([#45](https://github.com/shpaker/curlify3/issues/45)). `-b` reads such a value as the name of a cookie file and sent the cookies stored in it.
- The url of a starlette / FastAPI request keeps its path as it arrived ([#48](https://github.com/shpaker/curlify3/issues/48)). `request.url` is built from the percent-decoded path, so `%20` gave a url curl rejects and `%2F`, `%3F`, `%23` came back as `/`, `?`, `#` — another route. The path now comes from the scope's `raw_path`. werkzeug / flask and django take it from `RAW_URI` / `REQUEST_URI` when the server sets them (gunicorn, uwsgi, werkzeug's own), since `PATH_INFO` is decoded too.
- A url holding `[`, `]`, `{` or `}` is rendered with `-g` / `--globoff` ([#48](https://github.com/shpaker/curlify3/issues/48)). curl expanded them as a glob: `{x}` lost its braces, `[1-3]` went out as three requests.
- A repeated header keeps every value ([#48](https://github.com/shpaker/curlify3/issues/48)). starlette and aiohttp kept only the first one; it is joined with `, ` now, and a repeated `Cookie` with `; ` — httpx, werkzeug and tornado joined cookies with a comma, which a server reads as part of the first cookie's value.
- A header with an empty value is rendered as `-H 'name;'` ([#48](https://github.com/shpaker/curlify3/issues/48)). curl drops `-H 'name: '` without sending it.
- A multipart command no longer sends two boundaries ([#50](https://github.com/shpaker/curlify3/issues/50)). `-F` makes curl pick a boundary of its own and append it to the `content-type` given with `-H`, which still carried the request's — `boundary=X; boundary=<curl's>`, and a server that reads the first one cannot parse the body. The `boundary` parameter is left out of the header now.
- A file part with an empty filename, which a browser sends for a file input left empty, is rendered as `-F 'f=;filename=""'` ([#50](https://github.com/shpaker/curlify3/issues/50)). `-F 'f=@'` names a file curl cannot open, so the command failed without sending anything.
- A part whose `filename` comes before its `name` keeps its field name ([#50](https://github.com/shpaker/curlify3/issues/50)). `name="` was matched inside `filename="` as well, so the filename named the field.
- Only `multipart/form-data` is taken apart into `-F` parts, matched case-insensitively ([#50](https://github.com/shpaker/curlify3/issues/50)). `multipart/related` and `multipart/mixed` carry no field names, so their parts were skipped one by one — a `multipart/related` body was left out of the command entirely. They go out as the body they are now, with the boundary they were written with.
- A werkzeug / flask request whose form was read before the command was rendered no longer loses its body ([#52](https://github.com/shpaker/curlify3/issues/52)). Parsing reads the stream to the end, so the command carried no `-d` without a word. An urlencoded form is encoded again from the parsed fields; a multipart one also held files and renders without `-d`, the way a consumed django stream already did.
- A GET that carries a body is rendered with `-X GET` ([#52](https://github.com/shpaker/curlify3/issues/52)). `-X` was left out for GET, and a body makes curl send POST.
- A HEAD request is rendered with `-I` / `--head` instead of `-X HEAD` ([#52](https://github.com/shpaker/curlify3/issues/52)), which kept curl waiting for a response body a HEAD response does not have.
- A `urllib.request.Request` with data and no content-type renders `content-type: application/x-www-form-urlencoded` ([#52](https://github.com/shpaker/curlify3/issues/52)), which urllib adds when it sends the request, rather than `text/plain`.
- A django request whose host is outside `ALLOWED_HOSTS` is rendered instead of raising `DisallowedHost` ([#52](https://github.com/shpaker/curlify3/issues/52)), so a logger that runs before django answers 400 still gets the command.
- A tornado client `HTTPRequest` renders the headers the client sets from its attributes when it sends it ([#52](https://github.com/shpaker/curlify3/issues/52)): `authorization` from `auth_username` / `auth_password` (basic), `user-agent` from `user_agent`, `accept-encoding: gzip` from `decompress_response`, and a form-encoded content-type for a POST without one.

## 0.14 (2026-10-16)

### Added
- `include_headers` / `exclude_headers` on `to_curl()` and `to_curl_async()` filter the rendered headers by name, case-insensitively ([#30](https://github.com/shpaker/curlify3/issues/30)). `include_headers` narrows first and `exclude_headers` subtracts from what is left. `Cookie` counts as a header, so dropping it drops `-b` too. Only the printed arguments change: leaving out `content-type` still renders a multipart body as `-F` parts. They are per-call arguments rather than module-level state, so a filter set in one place cannot change what other callers in the same process render. A bare `str`, or a name that is not a `str`, raises `TypeError`.
- Python 3.15 support: the `Programming Language :: Python :: 3.15` classifier, and 3.15 in the CI test matrix (the Windows end-to-end job now runs on 3.10 and 3.15).

## 0.13 (2026-08-21)

### Added
- Docstrings across the package: every adapter module carries a usage example for its library, and `to_curl()` / `to_curl_async()` document the accepted types, the options and the `ValueError` contract in matching terms.
- A FastAPI logging-middleware example in the README — reading the body in a middleware is safe there, starlette 0.28+ caches what the render consumed and replays it to the route handler.

### Changed
- The README is reorganized: the per-framework examples moved into the adapter docstrings, the quick start renders with `pretty=True`, and the comparison table moved after the reference sections.

## 0.12 (2026-08-20)

### Added
- Six new packages, seven new adapters. Still zero runtime dependencies: every adapter registers only when its library is importable.
  - `niquests` — `PreparedRequest`, sync. A self-contained copy of the `requests` adapter (the httpx2 precedent: a fork can diverge, the copy keeps that isolated). HTTP/2 and HTTP/3 are negotiated on the transport, so the command carries no `--http2`.
  - `urllib.request` (stdlib) — `Request`, sync. An absent method renders the one urllib would send (`POST` with `data`, `GET` otherwise), headers are merged from both the plain header dict and the unredirected ones, and a streaming body renders without `-d`.
  - `aiohttp` client-side — `ClientRequest`, async, reachable in client middlewares (aiohttp 3.12+). The body is read without being consumed via `Payload.as_bytes()` (aiohttp 3.12.1+): in-memory payloads hand back their value, file payloads seek back, async iterables are cached and replayed at send time; on older aiohttp only in-memory payloads are read and everything else renders without `-d`, because reading it would corrupt the outgoing request.
  - `django` — `HttpRequest`, sync (the framework buffers the body before the view runs), covering `WSGIRequest` and `ASGIRequest`. The absolute url comes from `build_absolute_uri()`; a stream consumed without buffering (multipart parsing, `request.read()`) raises `RawPostDataException` inside Django, and the command then carries the headers but no `-d`.
  - `flask` / `werkzeug` — `werkzeug.wrappers.Request`, sync. Covers Flask through its Werkzeug base, the way the starlette adapter covers FastAPI; the body is read with `get_data(cache=True, parse_form_data=False)`, so form parsing after rendering still works.
  - `tornado` — client `httpclient.HTTPRequest` and server `httputil.HTTPServerRequest`, both sync. The server url comes from `full_url()`.

### Fixed
- A body or a multipart field value that starts with `@` — or `<` for a field value — no longer makes the rendered command read a **local file** and send it to the url the request was rendered for. `curl` reads those leading characters as the name of a file to load the value from, so `-d '@/etc/passwd'` sent the file rather than the body. Such a value is now rendered with the option that takes it literally, `--data-raw` or `--form-string`; a file *part* keeps `-F 'field=@file'`, where the `@` is the intended meaning. Reachable from the wire through the server-side adapters, where the value is the caller's to choose, and verified end-to-end against a real file.
- A multipart field carrying a value that is not valid UTF-8 no longer raises `UnicodeDecodeError`. Part names, field values and filenames are rendered through the same ANSI-C quoting a body that did not decode uses (`-F $'blob=caf\xe9'`), and `shell="powershell"` refuses them the way it already refuses a raw body.
- A multipart field value containing a newline was truncated at it. The value was matched as a single line, so the command silently sent a prefix of what the request carried. The parts are split on the boundary from `Content-Type` now instead, which also means they are rendered in the order the body carries them — the two patterns this replaced ran one after the other, so every plain field came out before every file part whatever order the body put them in. A `multipart` content-type with no `boundary` parameter leaves nothing to take the body apart with and renders without `-F`.
- A single-character multipart field name was dropped from the command without a word: both part patterns required two characters of a name, so `-F 'a=1'` never appeared and the command silently sent less than the request did.
- A NUL byte in a multipart field value is rejected like one in a body. The multipart branch was exempt from the check on the grounds that it renders only names and filenames, which was not true of a plain field's value — the argument would have been truncated at the NUL and the command would have run, sending something other than the request.
- A `Cookie` header held in a case-sensitive container was silently dropped: the cookie extraction looked the header up case-insensitively, which not every wrapped container supports — tornado's client request keeps whatever plain dict it was handed — so the value reached neither `-b` nor `-H`. The extraction now scans the lowercased header names.
- An empty `Cookie` header no longer renders as `-H 'cookie: '`. It carries no cookies, and `-b` correctly stayed silent, but the header itself leaked through; django's `RequestFactory` puts one on every request it builds, which is how it surfaced.

## 0.11 (2026-08-17)

### Fixed
- **A value containing a single quote could execute arbitrary commands in the reader's shell.** `sh` output wrapped every value in `'…'` without escaping, so a quote inside a header, cookie, url or body closed the literal and the rest of the value was parsed as shell code. This is reachable from the wire through the server-side adapters, where the request path, cookies and headers are chosen by the client: an incoming `GET /x;id` used to render as `curl … http://host/x;id`, which runs `id` when the developer pastes it out of a log. Every value is now quoted, and the url and cookie header are quoted whenever they hold anything outside the safe character class that `shlex.quote()` uses.
- A url with a single query parameter is now quoted. It has no `&`, so it used to be emitted bare, and `zsh` — the default shell on macOS — refuses the bare `?` as an unmatched glob with `no matches found`, so the command did not run at all.
- A body that is not valid UTF-8 is rendered as `--data-raw $'\xff\xfe'` instead of the Python `repr` of the `bytes` object inside `-d '…'`, which produced a command that could not run. The escape form is ANSI-C quoting: `bash`, `zsh` and `ksh` expand it, POSIX `sh` does not, and only the bytes that have to be escaped are, so a mis-encoded text body stays readable as `$'caf\xe9'`. `--data-raw` rather than `-d`, because both `-d` and `--data-binary` read a leading `@` as a filename to load the body from. The same body with `shell="powershell"` now raises `ValueError`: raw bytes cannot be spelled behind the `--%` stop-parsing token.
- A body containing a NUL byte raises `ValueError` instead of rendering a command that runs and sends a truncated body. A command-line argument is NUL-terminated, so no quoting can carry one. A NUL is valid UTF-8, so this is checked on the text path as well as the `bytes` one; a multipart body is unaffected, since only its part names and filenames are rendered.
- The `Content-Type` fallback for a body sent without one is `text/plain`, not the reversed `plain/text`.

### Added
- End-to-end coverage for the cases above: the single-quoted payload now runs under `bash` as well as PowerShell, and two new `sh` cases replay a body of every byte value except NUL, and a body starting with `@`, byte-for-byte through a real shell.
- `LICENSE` (MIT) and trove classifiers. The package was published without either; the `pyversions` badge in the README rendered as `python missing` because the classifiers it reads were absent.

## 0.10 (2026-08-17)

### Added
- Type annotations across the whole package, and a `py.typed` marker so they are visible to type checkers in projects that depend on `curlify3` (PEP 561). `to_curl()` / `to_curl_async()` are declared as returning `str` and accepting `shell`, `pretty` and `long_options`; the `ValueError` contract for an unknown `shell` value is unchanged, so `shell` stays a plain `str`.
- [`ty`](https://docs.astral.sh/ty/) as the type checker and a `lint` CI job that runs it together with `ruff` on every pull request and on pushes to `main`.
- Dependabot configuration for `uv` (`pyproject.toml` + `uv.lock`) and for GitHub Actions, weekly and grouped so tooling and test dependencies arrive as separate pull requests.

### Changed
- [`ruff`](https://docs.astral.sh/ruff/) replaces `black` and `isort`, which were declared as dev dependencies but never enforced anywhere. The formatting rules are carried over: line length 120, preserved string quotes, one blank line between plain and `from` imports.
- The sync and async request-data bases are siblings over a shared generic base instead of the async one inheriting the sync one. An `async def body()` cannot override a sync `def body()`, which made the `starlette` adapter — registered as async, but inheriting the sync base — a type error.
- The `httpx2` adapter shares the common base again instead of duplicating it. The base grew a type parameter for the wrapped request in this release, which is what kept the `httpx2` copy separate; `--http2` stays in the output.
- The release workflow anchors its version replacement on the `version` lines instead of replacing every occurrence of the literal `0.1.0`, which is also a plausible dependency bound now that Dependabot writes into `pyproject.toml`. The step asserts the replaced value afterwards, so a substitution that matched nothing stops the release instead of publishing the placeholder.

### Fixed
- The `starlette` adapter resolved `starlette.requests.Request` through a bare `import starlette`, which worked only because an unused import of the same module happened to register the submodule. It imports `Request` directly now.
- A request whose `Content-Type` announces `multipart` while carrying no body no longer raises `TypeError`; it renders without `-F`. Reachable with `requests` when the header is set by hand.
- A `requests` body that is an iterable or a file-like object (a streaming payload) is no longer rendered as its Python `repr` inside `-d`. Such a payload has no textual form a shell could replay, so the command now carries no `-d` at all.
- Header values are decoded to text before they are rendered. `requests` types its header values as `str | bytes`, and a `bytes` value used to reach `"multipart" in content_type` and raise `TypeError`.

## 0.9 (2026-08-17)

### Added
- Readable output ([#6](https://github.com/shpaker/curlify3/issues/6)): `pretty=True` on `to_curl()` / `to_curl_async()` puts the url on the first line and every option on its own, `long_options=True` renders `--request` / `--header` / `--cookie` / `--data` / `--form` instead of the short names. The two are independent and both default to `False`, so the one-line output is unchanged. `pretty=True` raises `ValueError` for `shell="powershell"`, where the `--%` token is effective only until the next newline.

## 0.8 (2026-08-17)

### Added
- PowerShell output ([#7](https://github.com/shpaker/curlify3/issues/7)): `shell="powershell"` on `to_curl()` / `to_curl_async()` renders `curl.exe --% …` for Windows PowerShell 5.1, quoted by Windows command-line rules so arbitrary JSON survives. Without the stop-parsing token, 5.1's argument binder mangles the body however it is escaped; on `pwsh` 7.2+ run `$PSNativeCommandArgumentPassing = 'Legacy'` first, and note that `%NAME%` references in a payload are expanded. Constants `curlify3.SH` and `curlify3.POWERSHELL` are exported; default `shell="sh"` output is unchanged.
- End-to-end shell tests (`test_shell_e2e.py`): the generated command is run by a real shell — bash, plus `powershell.exe` and `pwsh` on a new `windows-latest` CI job — against a local server that checks the request arrives byte-for-byte.

## 0.7 (2026-06-05)

### Changed
- README restructured along Python-packaging best practices: added Features, structured Usage section with per-client examples (`requests`, `httpx` sync/async, `httpx2`, server-side `aiohttp` and `starlette` / `fastapi`), API reference, supported-objects matrix, payload-handling table, and a Development section.
- Added a comparison table against `curlify` and `curlify2` so users can pick the right package at a glance.
- Added CI / Python-versions badges to README.

## 0.6 (2026-06-05)

### Added
- `httpx2` adapter (sync + async). When the input is an `httpx2.Request`, the generated curl command includes `--http2`. The adapter is fully self-contained so future divergence from `httpx` stays isolated.

### Changed
- Minimum Python is now `3.10` (was `3.8`).
- Project migrated from Poetry to **uv** (`uv.lock`, `uv sync`, `uv build`, `uv publish`). Build backend switched from `poetry-core` to `hatchling`.
- `Justfile` now drives commands through `uv run …`.
- CI workflow renamed `Lint` → `Tests`; matrix is `3.10 → 3.14`; runs on `astral-sh/setup-uv@v5`.
- Release workflow (`pypi.yml`) uses `uv build` + `uv publish`.
- Dropped unused `pytest-httpx` dev dependency.
- Test expectations updated for `httpx>=0.28` (compact JSON separators) and dynamic `Accept-Encoding`/`User-Agent` capture for aiohttp tests so they stop breaking on aiohttp version bumps.
- README refreshed: lists `httpx2` in supported clients, documents the Python 3.10+ requirement, adds httpx2 and async usage examples.

## 0.5 (2024-11-08)

### Added
- Python 3.8 support — typing imports relaxed so the package installs on older interpreters.

## 0.4 (2024-11-08)

### Fixed
- `requests` adapter no longer crashes when the prepared body is a plain text file payload (`-d '…'` is now produced correctly).

## 0.3 (2024-11-08)

### Added
- `aiohttp` server-side adapter — `to_curl_async(aiohttp.web.Request)` renders the incoming request as a curl command.

## 0.2 (2024-11-07)

### Fixed
- Filled in `repository` metadata in `pyproject.toml` so PyPI links back to GitHub.

## 0.1 (2024-11-07)

### Added
- Initial release.
- `to_curl(request)` and `to_curl_async(request)` for `requests.PreparedRequest`, `httpx.Request`, and `starlette.requests.Request`.
- Multipart, form, JSON, text, and binary file payload support; cookies passed via `-b`.
