# Development

The project uses [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/). [CONTRIBUTING.md](https://github.com/shpaker/curlify3/blob/main/CONTRIBUTING.md) has the conventions and the pull request flow.

```console
$ uv sync --group dev
$ just tests   # pytest
$ just lint    # ruff format --check, ruff check, ty check
$ just fmt     # ruff check --fix, then ruff format
$ just docs    # build this documentation into docs/_build/html
```

`just fmt` runs the linter before the formatter on purpose: a `--fix` can leave code the formatter still has to lay out. Formatting and linting are handled by [`ruff`](https://docs.astral.sh/ruff/), type checking by [`ty`](https://docs.astral.sh/ty/).

One convention the tooling cannot enforce on its own: every parameter of a function goes on its own line, so every parameter list ends with a trailing comma. Write the comma and the formatter keeps the layout.

## Tests

| Suite | Covers |
| --- | --- |
| `test_curlify3.py` | every adapter and option, the rendered command compared verbatim |
| `test_shell_e2e.py` | the rendered command run in a real shell against a local server |
| `test_pytest_plugin.py` | the pytest plugin, through generated test files |
| `test_robot.py` | the Robot Framework library, unit tests and suites run through `robot.run` |

CI runs the linter and the type checker on every pull request, and the test suite on Python 3.10–3.15. A separate `windows-latest` job runs the end-to-end tests against the real `powershell.exe` 5.1 and `pwsh`, so the PowerShell dialect is verified by the shell it targets rather than by string comparison alone. The POSIX end-to-end tests do the same through `bash`: the command is executed and the server checks that the request arrived byte for byte.

## Documentation

These pages live in `docs/` as Markdown, built with [Sphinx](https://www.sphinx-doc.org/) and [MyST](https://myst-parser.readthedocs.io/). `just docs` builds them with warnings as errors, as CI does on every pull request; a push to `main` publishes them to GitHub Pages.

## Releases

A GitHub release named after the version, such as `0.15`, publishes the package to PyPI: the release workflow writes the version into `pyproject.toml` and `curlify3/__init__.py`, builds and uploads. Before tagging, the `Unreleased` section of the changelog gets the version and the date.
