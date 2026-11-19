#!/usr/bin/env bash
# Start the Hermes backend (Micro Drama SaaS).
# Selalu jalan dari direktori backend ini — .env dibaca relatif ke
# direktori ini (lihat app/core/config.py), jadi server tidak boleh
# dijalankan dari CWD lain tanpa script ini.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8001}"
