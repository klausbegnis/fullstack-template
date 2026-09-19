#!/bin/sh
set -eu

python -m app.commands.wait_for_database
alembic upgrade head
exec "$@"
