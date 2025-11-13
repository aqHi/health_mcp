#!/usr/bin/env bash
set -euo pipefail

# Ensure python can find the application module when invoked from the project root.
export PYTHONPATH="${PYTHONPATH:-}:/app"

echo "Waiting for database to be ready..."
python - <<'PY'
import logging
import os
import sys

from app.db_init import initialize_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

attempts_env = os.getenv("DB_INIT_MAX_ATTEMPTS")
delay_env = os.getenv("DB_INIT_DELAY_SECONDS")

attempts = None
delay = None

try:
    if attempts_env:
        attempts = int(attempts_env)
        logging.info("Using custom DB init attempts from env: DB_INIT_MAX_ATTEMPTS=%s", attempts_env)
    if delay_env:
        delay = float(delay_env)
        logging.info("Using custom DB init delay from env: DB_INIT_DELAY_SECONDS=%s", delay_env)
except ValueError:
    logging.exception("Invalid DB init configuration. Ensure attempts is int and delay is float.")
    sys.exit(1)

try:
    initialize_database(attempts=attempts, delay=delay)
except Exception as exc:  # pragma: no cover - depends on external service
    logging.exception("Failed to initialize database")
    sys.exit(1)
PY

echo "Database ready. Launching application."
exec "$@"
