# Robot Framework library

`curlify3.robot` brings the same rendering to Robot Framework suites, with a hook into RequestsLibrary sessions. It needs the `robot` extra:

```console
$ pip install curlify3[robot]
```

The extra installs Robot Framework 6.1 or newer. The core package keeps zero runtime dependencies: only `curlify3.robot` imports Robot Framework.

## Example

```robotframework
*** Settings ***
Library    RequestsLibrary
Library    curlify3.robot    exclude_headers=${{["user-agent", "accept-encoding"]}}

*** Test Cases ***
Render One Request
    ${resp}=       GET        https://httpbin.org/get
    ${cmd}=        To Curl    ${resp}    pretty=True
    Log As Curl    ${resp}    level=DEBUG

Log Every Request Of A Session
    Create Session          httpbin    https://httpbin.org
    Enable Curl Logging     httpbin    mask_headers=${{["authorization"]}}
    GET On Session          httpbin    /get
    POST On Session         httpbin    /post    json=${{ {"date": "2026-08-10"} }}
    Disable Curl Logging    httpbin
```

The library is imported as `Library    curlify3.robot`; the class path `curlify3.robot.CurlifyLibrary` names the same library.

## Keywords

| Keyword | Does |
| --- | --- |
| `To Curl    request` | returns the command |
| `Log As Curl    request    level=INFO` | writes the command to the log and returns it |
| `Enable Curl Logging    alias    level=INFO` | logs every request sent through the RequestsLibrary session `alias` |
| `Disable Curl Logging    alias` | stops that |

`request` is any request object `to_curl()` accepts, or a response carrying one in its `request` attribute — so the `${resp}` the RequestsLibrary keywords return goes in as is.

`Enable Curl Logging` registers a response hook on the session and covers the `* On Session` keywords. Enabling it again for the same session replaces the earlier arguments rather than logging each request twice. A request sent with a session-less keyword (`GET`, `POST` …) goes through `Log As Curl    ${resp}` instead. A missing alias, or a RequestsLibrary version whose sessions cannot be reached, raises a clear error.

## Arguments

Every keyword takes the options of {py:func}`~curlify3.to_curl`:

| Argument | Default |
| --- | --- |
| `shell` | `sh` |
| `pretty` | `False` |
| `long_options` | `False` |
| `include_headers` | all headers |
| `exclude_headers` | none |
| `mask_headers` | none |

The logging keywords also take `level`: `TRACE`, `DEBUG`, `INFO` (the default), `CONSOLE`, `WARN` or `ERROR`. `HTML` is not offered, since the command would be rendered as markup rather than shown as text to copy.

Given as library import arguments, the same options — `level` included — become the defaults every keyword falls back to; a keyword argument overrides them for one call:

```robotframework
*** Settings ***
Library    curlify3.robot    pretty=True    mask_headers=${{["authorization", "cookie"]}}

*** Test Cases ***
One Line This Time
    ${cmd}=    To Curl    ${resp}    pretty=False
```

Header lists are Python lists, written with Robot's `${{ … }}` inline evaluation.
