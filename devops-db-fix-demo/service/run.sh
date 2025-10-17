#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
# ENVIRONMENT can be "test" or "prod" when you run this script
uvicorn app:app --host 0.0.0.0 --port 8000
