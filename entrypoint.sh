#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Creating admin user..."
python -m app.scripts.create_admin

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
