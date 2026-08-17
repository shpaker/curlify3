tests: pytest
lint: format-check check types

# the linter runs first: its fixes can leave code the formatter still has to lay out
fmt:
  uv run ruff check . --fix
  uv run ruff format .

format-check:
  uv run ruff format --check .

check:
  uv run ruff check .

types:
  uv run ty check

pytest:
  uv run pytest -vv
