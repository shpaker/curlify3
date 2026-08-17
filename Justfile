tests: pytest
lint: format-check check types

fmt:
  uv run ruff format .
  uv run ruff check . --fix

format-check:
  uv run ruff format --check .

check:
  uv run ruff check .

types:
  uv run ty check

pytest:
  uv run pytest -vv
