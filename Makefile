install:
	uv sync

project:
	uv run project

build:
	uv build

publish:
	uv publish --dry-run

package-install:
	python3 -m pip install dist/*.whl

lint:
	uv run ruff check .