.PHONY: setup test lint typecheck db-up migrate

setup:
	uv sync --group dev

test:
	uv run pytest

lint:
	uv run ruff check src tests migrations/env.py migrations/versions

typecheck:
	uv run mypy

db-up:
	docker compose up -d --remove-orphans

migrate:
	uv run alembic upgrade head
