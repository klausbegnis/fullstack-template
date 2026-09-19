# Backend

FastAPI backend template with async SQLAlchemy, Alembic migrations, and a
cookie-based authentication vertical (login, refresh rotation, CSRF, logout).

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16

## Local development

Install dependencies:

```bash
uv sync
```

Copy `.env.example` to `.env` and adjust the values for your environment,
then run the database migrations and start the API:

```bash
uv run alembic upgrade head
uv run python main.py
```

## Tests

```bash
uv run pytest
uv run ruff format --check .
uv run ruff check .
```

Integration tests that require PostgreSQL are skipped automatically unless
the `DATABASE_URL` environment variable is set.
