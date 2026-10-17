# Comparison with curlify and curlify2

| | [`curlify`](https://pypi.org/project/curlify/) | [`curlify2`](https://pypi.org/project/curlify2/) | **`curlify3`** |
| --- | :---: | :---: | :---: |
| `requests` | ✅ | ✅ | ✅ |
| `httpx` | ❌ | ✅ | ✅ |
| `httpx2` (HTTP/2) | ❌ | ❌ | ✅ |
| `niquests` | ❌ | ❌ | ✅ |
| `urllib.request` (stdlib) | ❌ | ❌ | ✅ |
| `aiohttp` (client and server) | ❌ | ❌ | ✅ |
| `tornado` (client and server) | ❌ | ❌ | ✅ |
| `starlette` / `fastapi` (server-side) | ❌ | ❌ | ✅ |
| `django` (server-side) | ❌ | ❌ | ✅ |
| `flask` / `werkzeug` (server-side) | ❌ | ❌ | ✅ |
| Async API | ❌ | ❌ | ✅ |
| PowerShell output | ❌ | ❌ | ✅ |
| Header filtering and masking | ❌ | ❌ | ✅ |
| pytest / Robot Framework integration | ❌ | ❌ | ✅ |
| Python | 3.7+ | 3.7–3.11 | 3.10+ |

`curlify` is the original and covers only `requests`. `curlify2` added `httpx` but is sync-only, client-side-only, and has not seen a release since 2023. `curlify3` extends the same idea across the ecosystem: HTTP/2 (`httpx2`), an async entrypoint, the rest of the popular clients down to the stdlib's `urllib.request`, and server-side adapters for `aiohttp`, `starlette` / `fastapi`, `django`, `flask` / `werkzeug` and `tornado`, so incoming requests can be dumped as `curl` from inside a handler.
