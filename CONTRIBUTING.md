# Contributing

Thanks for helping out. Security issues are not reported here — see [SECURITY.md](SECURITY.md).

## Setup

The tooling is described in the README's [Development](README.md#development) section. In short:

```sh
uv sync --group dev
just tests   # pytest
just lint    # ruff format --check, ruff check, ty check
just fmt     # ruff check --fix, then ruff format
```

`just lint` and `just tests` are what CI runs, so a pull request that passes both locally should pass there too. The PowerShell end-to-end tests run only on Windows; CI covers them.

## Conventions

- Every parameter of a function goes on its own line, so every parameter list ends with a trailing comma. The formatter keeps the layout once the comma is there, but cannot add it for you:

  ```python
  def quote_sh(
      value: str,
  ) -> str:
  ```

- Comments explain why, not what — the existing modules are the reference for tone and density.
- A behavior change comes with a test in `test_curlify3.py`. A change to quoting or to a shell dialect also gets an end-to-end case in `test_shell_e2e.py`, which runs the rendered command in the real shell. The pytest plugin and the Robot Framework library have suites of their own, `test_pytest_plugin.py` and `test_robot.py`.

## Adding an adapter

1. A module `curlify3/_req_<library>.py` with a docstring that carries a usage example, following the existing ones.
2. Registration in `curlify3/_utils.py` under `suppress(ImportError)`, so the package keeps zero runtime dependencies. The first adapter that accepts a request wins, so a more specific type goes before the one it could be mistaken for.
3. The library in the `dev` dependency group, tests, and rows in the README's supported-request-objects and comparison tables.

## Changelog

Every user-visible change gets an entry in [CHANGELOG.md](CHANGELOG.md), under `Added`, `Changed` or `Fixed` at the top. Describe the behavior a user sees, not the diff, and link the issue. Changes that do not reach the package (CI, docs, tests) need no entry.

## Pull requests

1. Open an issue first, unless the change is trivial, so the approach can be agreed before the work.
2. Branch from `main`, and title the pull request in the conventional-commit style the history uses: `feat:`, `fix:`, `docs:`, `chore:`.
3. Put `Closes #N` in the description, and keep the pull request to one change.
4. CI must be green before review.
