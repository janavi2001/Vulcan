#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
# ENVIRONMENT=test or prod before running
uvicorn app:app --host 0.0.0.0 --port 8000
