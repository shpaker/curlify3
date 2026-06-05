SOURCE_DIR := "curlify3"

tests: pytest
fmt: isort black

isort:
  uv run isort {{ SOURCE_DIR }} --diff
  uv run isort test_curlify3.py --diff

black:
  uv run isort {{ SOURCE_DIR }}
  uv run isort test_curlify3.py

pytest:
  uv run pytest -vv
