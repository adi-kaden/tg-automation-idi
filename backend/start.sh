#!/bin/bash

# Run alembic migrations
alembic upgrade head

# --- Helper: run a process in a restart loop ---
run_with_restart() {
    local name="$1"
    shift
    while true; do
        echo "[supervisor] Starting $name..."
        "$@"
        exit_code=$?
        echo "[supervisor] $name exited with code $exit_code — restarting in 5s..."
        sleep 5
    done
}

# Start Celery worker in background with auto-restart
run_with_restart "celery-worker" \
    celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2 &

# Start Celery beat in background with auto-restart
run_with_restart "celery-beat" \
    celery -A app.tasks.celery_app beat --loglevel=info &

# Start uvicorn (foreground - keeps container alive)
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
