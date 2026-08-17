# Changelog

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
