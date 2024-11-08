SOURCE_DIR := "curlify3"

tests: pytest
fmt: isort black

isort:
  poetry run isort {{ SOURCE_DIR }} --diff
  poetry run isort test_curlify3.py --diff

black:
  poetry run isort {{ SOURCE_DIR }}
  poetry run isort test_curlify3.py

pytest:
  poetry run pytest -vv
