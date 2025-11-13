#!/usr/bin/env bash
set -euo pipefail

# Ensure python can find the application module when invoked from the project root.
export PYTHONPATH="${PYTHONPATH:-}:/app"

echo "Waiting for database to be ready..."
python - <<'PY'
import logging
import sys

from app.db_init import initialize_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

try:
    initialize_database()
except Exception as exc:  # pragma: no cover - depends on external service
    logging.exception("Failed to initialize database")
    sys.exit(1)
PY

echo "Database ready. Launching application."
exec "$@"
