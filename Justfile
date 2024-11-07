SOURCE_DIR := "curlify3"

tests: pytest
fmt: isort black

isort:
  poetry run isort {{ SOURCE_DIR }} --diff --color

black:
  poetry run isort {{ SOURCE_DIR }}

pytest:
  poetry run pytest -vv
