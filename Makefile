.PHONY: help sync dev export upgrade test lint

help:
	@echo "Targets:"
	@echo "  sync    - Create/refresh .venv from uv.lock (or pyproject if first run)"
	@echo "  dev     - Sync with all extras (media, ui, aws, db, data, cli, dev)"
	@echo "  export  - Export locked environment to requirements.txt"
	@echo "  upgrade - Upgrade all locked dependencies (updates uv.lock)"
	@echo "  test    - Run tests via uv"
	@echo "  lint    - Run ruff via uv"

sync:
	uv sync

dev:
	uv sync --all-extras

export:
	uv export -o requirements.txt

upgrade:
	uv lock --upgrade

test:
	uv run pytest -q || true

lint:
	uv run ruff check . || true


