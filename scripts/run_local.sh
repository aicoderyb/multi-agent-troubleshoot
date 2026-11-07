#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"
pip install -e ".[dev]" -q
uvicorn mulat.main:app --reload --host 0.0.0.0 --port 8000
