# pytest plugin

The bundled pytest plugin records the HTTP requests a test sends and, when the test fails, attaches them to its report as commands to replay from a terminal.

```text
------------------------------ Captured curl call ------------------------------
# [1] 200
curl --http2 -X POST -H 'host: testserver' ... -d '{"user":"alice"}' http://testserver/login
# [2] 422
curl --http2 -X POST -H 'host: testserver' ... -d '{"qty":2}' http://testserver/orders
```

## Loading the plugin

Load it from the root `conftest.py`:

```python
pytest_plugins = ["curlify3.pytest_plugin"]
```

or on the command line with `-p curlify3.pytest_plugin`. It needs nothing beyond pytest itself.

It is not registered through a `pytest11` entry point on purpose: importing `curlify3` imports every installed library it has an adapter for, and that should not land on the startup of every pytest run in an environment that merely has `curlify3` installed.

## Turning the capture on

Loading the plugin records nothing yet. Turn the capture on for the whole run with `--curl-on-failure`, or in the ini file:

```ini
[pytest]
curl_on_failure = true
```

A failing test then reports every request it sent:

```python
from fastapi.testclient import TestClient

def test_create_order():
    client = TestClient(app)
    client.post("/login", json={"user": "alice"})
    resp = client.post("/orders", json={"qty": 2})
    assert resp.status_code == 201
```

- Entries are numbered in the order the requests went out, and labelled with the status of the response, the name of the exception the client raised, or nothing when the status is not known yet (a lazy `niquests` response is not forced).
- The labels are shell comments, so the section pastes into a terminal as a whole.
- With the global switch the capture starts with the test's setup, so the requests its fixtures send are listed too.
- Passing tests report nothing, and the captured commands are dropped once a test's run ends.

## The `curl_requests` fixture

To capture a single test, request the `curl_requests` fixture instead of the global switch. It returns the commands rendered so far, in the order the requests were sent, which also makes them available to assertions:

```python
import httpx

def test_profile(curl_requests):
    resp = httpx.get("https://api.example.com/me")
    assert resp.status_code == 200, curl_requests[-1]
```

A failing test that requested the fixture gets the report section as well. With the global switch on, the fixture returns the run's capture for that test.

## What is recorded

Requests are recorded by wrapping the clients' public `send` for the duration of a test:

| Client | Sync | Async |
| --- | :---: | :---: |
| `httpx` | `httpx.Client` | `httpx.AsyncClient` |
| `httpx2` | `httpx2.Client` | `httpx2.AsyncClient` |
| `requests` | `requests.Session` | — |
| `niquests` | `niquests.Session` | `niquests.AsyncSession` |

starlette's and FastAPI's `TestClient` is an `httpx2` client, so test clients of those apps are covered. `aiohttp` is not: its client would need a middleware rather than a wrapped method.

One call to `send` is one entry. `requests` follows a redirect by calling `send` again, so every hop is listed; `httpx` follows it inside `send`, so only the first request is.

The command is rendered as the request is sent, because a streaming body may be gone by the time the test fails. A request that cannot be rendered is listed as a `# not rendered: …` comment and never replaces the test's own failure.

## Options

| ini option | default | |
| --- | --- | --- |
| `curl_on_failure` | `false` | the same as `--curl-on-failure` |
| `curl_exclude_headers` | none | header names left out of the commands, one per line |
| `curl_mask_headers` | none | header names kept in the commands with `***` in place of their values, one per line |
| `curl_max_requests` | `20` | how many of the last requests a report lists, `0` for all; the report says how many earlier ones were omitted |

`curl_exclude_headers` and `curl_mask_headers` work as `exclude_headers` and `mask_headers` do, see [Filtering and masking headers](../guide/headers.md). A `curl_max_requests` that is not a non-negative integer is a usage error at startup.

## Keeping secrets out of CI logs

The commands carry the headers as sent, `Authorization` and cookies included, and test reports often end up in CI logs. Mask what should not be there:

```ini
[pytest]
curl_on_failure = true
curl_mask_headers =
    authorization
    cookie
    x-api-key
curl_exclude_headers =
    user-agent
    accept-encoding
```
