#!/bin/sh
set -e

case "$SERVICE_ROLE" in
  worker)
    echo "Starting Celery worker..."
    exec celery -A app.workers.tasks worker --loglevel=info --concurrency=4
    ;;
  beat)
    echo "Starting Celery beat..."
    exec celery -A app.workers.tasks beat --loglevel=info --schedule=/tmp/celerybeat-schedule
    ;;
  *)
    echo "Running migrations..."
    alembic upgrade head
    echo "Starting API server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
esac
